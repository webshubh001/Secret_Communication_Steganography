"""
routes/decode.py — Multi-image LSB steganography decoding route.

Full pipeline:
  1. Face authentication gate (must pass face auth before decoding)
  2. Accept uploaded stego images
  3. LSB-extract raw chunk bytes from each image
  4. Reconstruct and verify ciphertext (chunk hashes + full hash)
  5. Look up the SecretMessage record by session_id
  6. Decrypt AES key from DB using master secret
  7. AES-256-CBC decrypt the ciphertext
  8. Return plaintext message or downloadable file
"""

import os
import logging
import io
from datetime import datetime, timezone

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app, session, send_file
)
from flask_login import login_required, current_user

from models import db
from models.message import SecretMessage
from models.logs import AuthenticationLog, ActivityLog
from modules.steganography import extract
from modules.data_reconstruction import reconstruct_from_raw, ReconstructionError
from modules.encryption import decrypt_data, decrypt_aes_key

logger = logging.getLogger(__name__)
decode_bp = Blueprint('decode', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def _allowed_image(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def _is_face_authenticated() -> bool:
    """Return True only if the current user has passed face auth in this session."""
    return (
        session.get('face_authenticated') is True
        and session.get('face_auth_user_id') == current_user.id
    )


def _log_activity(user_id: int, activity: str, detail: str = None):
    log = ActivityLog(user_id=user_id, activity=activity, detail=detail)
    db.session.add(log)
    db.session.commit()


# ─── Decode Route ───────────────────────────────────────────────────────────────

@decode_bp.route('/decode', methods=['GET', 'POST'])
@login_required
def decode():
    # Face auth gate
    if not _is_face_authenticated():
        if not current_user.has_face_profile:
            flash(
                'You must register your face before you can decode messages.',
                'warning'
            )
            return redirect(url_for('face.register_face'))
        flash(
            'Face authentication is required to decode messages. '
            'Please authenticate your face first.',
            'warning'
        )
        return redirect(url_for('face.authenticate',
                                next=url_for('decode.decode')))

    if request.method == 'GET':
        return render_template('decode.html')

    # ── POST: Process decoding ──────────────────────────────────────────────────
    stego_files = request.files.getlist('stego_images')
    stego_files = [f for f in stego_files if f and f.filename]

    if not stego_files:
        flash('Please upload the stego images to decode.', 'danger')
        return render_template('decode.html')

    for f in stego_files:
        if not _allowed_image(f.filename):
            flash(f'"{f.filename}" is not an allowed image type.', 'danger')
            return render_template('decode.html')

    # 1. LSB-extract raw chunk bytes from each stego image
    raw_chunks = []
    for f in stego_files:
        image_bytes = f.read()
        # Save temporarily to extract
        tmp_path = os.path.join(
            current_app.config['EXTRACTED_FOLDER'],
            f'tmp_{current_user.id}_{f.filename}'
        )
        with open(tmp_path, 'wb') as out:
            out.write(image_bytes)

        try:
            raw = extract(tmp_path)
            raw_chunks.append(raw)
        except ValueError as exc:
            flash(f'Failed to extract data from "{f.filename}": {exc}', 'danger')
            os.remove(tmp_path)
            return render_template('decode.html')
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # 2. Reconstruct and verify
    try:
        ciphertext, session_id = reconstruct_from_raw(raw_chunks)
    except ReconstructionError as exc:
        _log_activity(current_user.id, 'decode_fail', str(exc))
        flash(str(exc), 'danger')
        return render_template('decode.html')

    # 3. Look up SecretMessage record
    msg = SecretMessage.query.filter_by(message_id=session_id).first()
    if msg is None:
        flash(
            f'No message record found for session ID "{session_id[:8]}...". '
            'This may have been created on a different system.',
            'danger'
        )
        return render_template('decode.html')

    # 4. Decrypt AES key
    master_secret = current_app.config['MASTER_SECRET']
    try:
        aes_key = decrypt_aes_key(msg.encrypted_aes_key, master_secret)
    except ValueError as exc:
        flash(f'Failed to recover the encryption key: {exc}', 'danger')
        return render_template('decode.html')

    # 5. AES decrypt
    try:
        plaintext = decrypt_data(ciphertext, aes_key)
    except ValueError as exc:
        _log_activity(current_user.id, 'decode_fail',
                      f'AES decrypt error: {exc}')
        flash(f'Decryption failed: {exc}', 'danger')
        return render_template('decode.html')

    # 6. Update record status
    msg.status = 'decoded'
    msg.decoded_at = datetime.now(timezone.utc)
    db.session.commit()

    # Clear face auth session flag after successful decode
    session.pop('face_authenticated', None)
    session.pop('face_auth_user_id', None)

    _log_activity(current_user.id, 'decode_success',
                  f'session_id={session_id} type={msg.data_type}')

    # 7. Return result
    if msg.data_type == 'text':
        try:
            decoded_text = plaintext.decode('utf-8')
        except UnicodeDecodeError:
            decoded_text = plaintext.decode('latin-1', errors='replace')
        return render_template('result.html',
                               decoded_text=decoded_text,
                               message=msg)
    else:
        # File download
        fname = msg.original_filename or 'decoded_file'
        return send_file(
            io.BytesIO(plaintext),
            as_attachment=True,
            download_name=fname
        )
