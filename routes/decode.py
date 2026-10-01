"""
routes/decode.py — Multi-image LSB steganography decoding route (v2).

Full pipeline (v2):
  Step 1: Upload stego images
  Step 2: Verify intended RECEIVER face (existing face-auth session flag)
  Step 3: Extract metadata → identify expected SENDER → verify SENDER face
  Step 4: LSB extraction + chunk reconstruction
  Step 5: SHA-256 integrity verification
  Step 6: LSTM sequence validation (Unit IV)
  Step 7: AES-256-CBC decryption
  Step 8: Return plaintext / file

Backward compatibility:
  Legacy messages (is_legacy == True, i.e. no receiver_id) skip the
  sender-face-verification step and show a legacy notice instead.
"""

import io
import logging
import os
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
from modules.face_authentication import verify_face
from modules.lstm_processor import lstm_processor

logger = logging.getLogger(__name__)
decode_bp = Blueprint('decode', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def _allowed_image(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def _is_receiver_face_authenticated() -> bool:
    """Return True only if the current user passed face auth in this session."""
    return (
        session.get('face_authenticated') is True
        and session.get('face_auth_user_id') == current_user.id
    )


def _log_activity(user_id: int, activity: str, detail: str = None):
    log = ActivityLog(user_id=user_id, activity=activity, detail=detail)
    db.session.add(log)
    db.session.commit()


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


# ── Decode Route ─────────────────────────────────────────────────────────────────

@decode_bp.route('/decode', methods=['GET', 'POST'])
@login_required
def decode():
    # ── Step 2 Gate: receiver face authentication ───────────────────────────────
    if not _is_receiver_face_authenticated():
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

    # ── Step 1 + 4: LSB-extract raw chunk bytes from each stego image ──────────
    raw_chunks = []
    for f in stego_files:
        image_bytes = f.read()
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
            return render_template('decode.html')
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ── Step 5: Reconstruct + SHA-256 verify ───────────────────────────────────
    try:
        ciphertext, session_id = reconstruct_from_raw(raw_chunks)
    except ReconstructionError as exc:
        _log_activity(current_user.id, 'decode_fail', str(exc))
        flash(str(exc), 'danger')
        return render_template('decode.html')

    # ── Look up SecretMessage record ────────────────────────────────────────────
    msg = SecretMessage.query.filter_by(message_id=session_id).first()
    if msg is None:
        flash(
            f'No message record found for session ID "{session_id[:8]}...". '
            'This may have been created on a different system.',
            'danger'
        )
        return render_template('decode.html')

    # ── Step 2 (DB check): verify this user is the intended receiver ────────────
    # For v2 messages, confirm the logged-in user is the intended recipient.
    if not msg.is_legacy and msg.receiver_id != current_user.id:
        # Log without storing biometric data
        _log_activity(
            current_user.id, 'decode_unauthorized',
            f'session_id={session_id[:8]} intended_receiver={msg.receiver_id}'
        )
        flash(
            'Access denied. This message was not encoded for you.',
            'danger'
        )
        return render_template('decode.html')

    # ── Step 3: Sender face verification (v2 only) ──────────────────────────────
    sender_verified = False
    sender_verification_skipped = False

    if msg.is_legacy:
        # Legacy message — sender/receiver face auth not available
        sender_verification_skipped = True
        sender_verified = True   # allow through with warning
        logger.info("Legacy message %s — sender face verification skipped.", session_id[:8])

    elif msg.sender_face_profile_id is None:
        # Sender's face profile was deleted after encoding
        sender_verification_skipped = True
        sender_verified = True
        flash(
            'Legacy message — enhanced sender/receiver face verification is unavailable '
            '(sender face profile no longer exists).',
            'warning'
        )

    else:
        # Retrieve the sender's registered face profile
        sender_face_profile = msg.sender_face_profile_ref
        if sender_face_profile is None:
            sender_verification_skipped = True
            sender_verified = True
            flash(
                'Sender face profile was deleted — skipping sender verification.',
                'warning'
            )
        else:
            # Require sender face image upload for verification
            if 'sender_face_image' not in request.files or \
               not request.files['sender_face_image'].filename:
                flash(
                    'Please upload an image of the expected sender for identity verification.',
                    'danger'
                )
                return render_template('decode.html',
                                       require_sender_face=True,
                                       sender_username=msg.sender.username if msg.sender else 'Unknown')

            sender_face_file = request.files['sender_face_image']
            if not _allowed_image(sender_face_file.filename):
                flash('Sender face image must be PNG, JPG, or JPEG.', 'danger')
                return render_template('decode.html')

            sender_face_bytes = sender_face_file.read()
            threshold = current_app.config.get('FACE_RECOGNITION_THRESHOLD', 0.6)
            stored_sender_embedding = sender_face_profile.get_embedding()

            # ── Core sender face verification ─────────────────────────────────
            sender_result = verify_face(sender_face_bytes, stored_sender_embedding, threshold)

            if sender_result.get('authenticated'):
                sender_verified = True
                # Log success WITHOUT the distance (to minimise biometric data in logs)
                _log_auth(
                    current_user.id, 'sender_face', 'success',
                    f'session_id={session_id[:8]}'
                )
                _log_activity(
                    current_user.id, 'sender_face_verified',
                    f'session_id={session_id[:8]}'
                )
                logger.info(
                    "Sender face verification PASSED for session %s", session_id[:8]
                )
            else:
                # FAIL — do NOT reconstruct or decrypt
                error_msg = sender_result.get('error', '')
                # Log the failure without biometric distance data to avoid
                # storing sensitive face comparison metrics in the audit log.
                _log_auth(
                    current_user.id, 'sender_face', 'failure',
                    f'session_id={session_id[:8]} reason=distance_exceeded'
                )
                _log_activity(
                    current_user.id, 'sender_face_failed',
                    f'session_id={session_id[:8]}'
                )
                if error_msg:
                    flash(
                        f'Sender face verification failed: {error_msg}. '
                        'Message access denied.',
                        'danger'
                    )
                else:
                    flash(
                        'Sender face verification failed. '
                        'The person in the uploaded image does not match the expected sender. '
                        'Message access denied.',
                        'danger'
                    )
                return render_template('decode.html')

    if not sender_verified:
        flash('Sender face verification failed. Message access denied.', 'danger')
        return render_template('decode.html')

    # ── Step 6: LSTM sequence validation (Unit IV) ──────────────────────────────
    # Re-process the extracted ciphertext through the LSTM and validate.
    # The LSTM acts as an additional neural-network-level integrity check.
    lstm_validation = lstm_processor.decode_sequence(
        ciphertext,
        stored_features=None,   # features were not persisted in DB (see encode.py note)
        # When features ARE stored, pass them here. For this implementation,
        # the LSTM validation uses the extracted bytes directly (self-validating).
    )
    if not lstm_validation.get('skipped') and not lstm_validation.get('valid'):
        _log_activity(
            current_user.id, 'decode_lstm_fail',
            f'session_id={session_id[:8]} similarity={lstm_validation.get("similarity")}'
        )
        flash(
            'LSTM sequence validation failed — the encrypted payload may be corrupted. '
            'Decryption aborted.',
            'danger'
        )
        return render_template('decode.html')

    # ── Step 7: Decrypt AES key ─────────────────────────────────────────────────
    master_secret = current_app.config['MASTER_SECRET']
    try:
        aes_key = decrypt_aes_key(msg.encrypted_aes_key, master_secret)
    except ValueError as exc:
        flash(f'Failed to recover the encryption key: {exc}', 'danger')
        return render_template('decode.html')

    # ── Step 7 cont: AES decrypt ────────────────────────────────────────────────
    try:
        plaintext = decrypt_data(ciphertext, aes_key)
    except ValueError as exc:
        _log_activity(current_user.id, 'decode_fail',
                      f'AES decrypt error: {exc}')
        flash(f'Decryption failed: {exc}', 'danger')
        return render_template('decode.html')

    # ── Update record status ────────────────────────────────────────────────────
    msg.status = 'decoded'
    msg.decoded_at = datetime.now(timezone.utc)
    db.session.commit()

    # Clear face auth session flag
    session.pop('face_authenticated', None)
    session.pop('face_auth_user_id', None)

    _log_activity(
        current_user.id, 'decode_success',
        f'session_id={session_id} type={msg.data_type} '
        f'sender_verified={sender_verified} '
        f'sender_skipped={sender_verification_skipped} '
        f'legacy={msg.is_legacy}'
    )

    # ── Step 8: Return result ───────────────────────────────────────────────────
    if msg.data_type == 'text':
        try:
            decoded_text = plaintext.decode('utf-8')
        except UnicodeDecodeError:
            decoded_text = plaintext.decode('latin-1', errors='replace')

        return render_template(
            'result.html',
            decoded_text=decoded_text,
            message=msg,
            sender_verification_skipped=sender_verification_skipped,
            lstm_validation=lstm_validation,
        )
    else:
        fname = msg.original_filename or 'decoded_file'
        return send_file(
            io.BytesIO(plaintext),
            as_attachment=True,
            download_name=fname
        )
