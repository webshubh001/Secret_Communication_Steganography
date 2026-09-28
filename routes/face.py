"""
routes/face.py — Face registration and authentication routes.

Routes:
  GET  /face/register       → Show face registration form
  POST /face/register       → Upload face image, generate embedding, store in DB
  GET  /face/authenticate   → Show face authentication form
  POST /face/authenticate   → Verify face, set session flag
  POST /face/delete         → Remove face profile from DB
"""

import os
import uuid
import logging
from datetime import datetime, timezone

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app, session, jsonify
)
from flask_login import login_required, current_user

from models import db
from models.user import FaceProfile
from models.logs import AuthenticationLog, ActivityLog
from modules.face_authentication import get_face_embedding, verify_face
from extensions import limiter

logger = logging.getLogger(__name__)
face_bp = Blueprint('face', __name__)

ALLOWED_FACE_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def _allowed_face_file(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_FACE_EXTENSIONS
    )


def _log_auth(user_id: int, auth_type: str, status: str, detail: str = None):
    log = AuthenticationLog(
        user_id=user_id,
        authentication_type=auth_type,
        status=status,
        detail=detail,
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()


def _log_activity(user_id: int, activity: str, detail: str = None):
    log = ActivityLog(user_id=user_id, activity=activity, detail=detail)
    db.session.add(log)
    db.session.commit()


# ─── Face Registration ──────────────────────────────────────────────────────────

@face_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_face():
    if request.method == 'POST':
        if 'face_image' not in request.files:
            flash('No file uploaded. Please select a face image.', 'danger')
            return render_template('face_register.html')

        f = request.files['face_image']
        if not f or f.filename == '':
            flash('No file selected.', 'danger')
            return render_template('face_register.html')

        if not _allowed_face_file(f.filename):
            flash('Only PNG, JPG, or JPEG images are allowed for face registration.', 'danger')
            return render_template('face_register.html')

        image_bytes = f.read()
        if len(image_bytes) == 0:
            flash('Uploaded file is empty.', 'danger')
            return render_template('face_register.html')

        # Generate embedding (will raise ValueError if no/multiple faces)
        try:
            embedding = get_face_embedding(image_bytes)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('face_register.html')

        # Save or update the FaceProfile
        profile = current_user.face_profile
        if profile is None:
            profile = FaceProfile(user_id=current_user.id)
            db.session.add(profile)

        profile.set_embedding(embedding)
        profile.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        _log_activity(current_user.id, 'face_register', 'Face embedding updated')
        flash('Face registered successfully! You can now use face authentication.', 'success')
        return redirect(url_for('dashboard.dashboard'))

    return render_template('face_register.html')


# ─── Face Authentication ────────────────────────────────────────────────────────

@face_bp.route('/authenticate', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per minute")
def authenticate():
    if request.method == 'POST':
        if not current_user.has_face_profile:
            flash('No face profile registered. Please register your face first.', 'warning')
            return redirect(url_for('face.register_face'))

        if 'face_image' not in request.files:
            flash('No face image provided.', 'danger')
            return render_template('face_auth.html')

        f = request.files['face_image']
        if not f or f.filename == '':
            flash('No file selected.', 'danger')
            return render_template('face_auth.html')

        if not _allowed_face_file(f.filename):
            flash('Only PNG, JPG, or JPEG images are allowed.', 'danger')
            return render_template('face_auth.html')

        image_bytes = f.read()
        threshold = current_app.config.get('FACE_RECOGNITION_THRESHOLD', 0.6)
        stored_embedding = current_user.face_profile.get_embedding()

        result = verify_face(image_bytes, stored_embedding, threshold)

        if result.get('authenticated'):
            # Set a session flag that the decode route will check
            session['face_authenticated'] = True
            session['face_auth_user_id'] = current_user.id
            _log_auth(current_user.id, 'face', 'success',
                      f"distance={result['distance']}")
            _log_activity(current_user.id, 'face_auth_success',
                          f"distance={result['distance']}")
            flash('Face authentication successful!', 'success')
            next_page = request.args.get('next') or url_for('decode.decode')
            return redirect(next_page)
        else:
            error_msg = result.get('error', '')
            detail = f"distance={result['distance']}" if result['distance'] else error_msg
            _log_auth(current_user.id, 'face', 'failure', detail)
            if error_msg:
                flash(f'Face authentication failed: {error_msg}', 'danger')
            else:
                flash(
                    f"Face not recognised (distance={result['distance']}, "
                    f"threshold={threshold}). Please try again.",
                    'danger'
                )

    return render_template('face_auth.html',
                           has_face=current_user.has_face_profile)


# ─── Delete Face Profile ────────────────────────────────────────────────────────

@face_bp.route('/delete', methods=['POST'])
@login_required
def delete_face():
    profile = current_user.face_profile
    if profile:
        db.session.delete(profile)
        db.session.commit()
        _log_activity(current_user.id, 'face_delete', 'Face profile removed')
        flash('Face profile deleted successfully.', 'info')
    else:
        flash('No face profile to delete.', 'warning')
    return redirect(url_for('dashboard.profile'))
