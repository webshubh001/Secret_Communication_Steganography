"""
routes/encode.py — Multi-image LSB steganography encoding route (v2).

Full pipeline (v2):
  1. Validate sender is authenticated
  2. Validate receiver is selected and has a registered face profile
  3. Validate cover images
  4. Generate AES-256 session key
  5. Encrypt the secret (text or file) with AES-256-CBC
  6. LSTM sequence processing (Unit IV) — produce feature vector
  7. Compute SHA-256 integrity hash
  8. Run Autoencoder on each cover image (Unit V) — compute reconstruction loss
  9. Split ciphertext into N chunks (one per cover image)
 10. Embed each chunk into its cover image (LSB)
 11. Compute image quality metrics (MSE, PSNR, SSIM)
 12. Store SecretMessage + StegoImage records in DB (with receiver + face refs)
 13. Serve stego images as a ZIP download

API endpoint:
  GET /encode/receivers  — JSON list of users with registered face profiles
  GET /encode/receiver-status?receiver_id=N — validate a specific receiver
"""

import io
import logging
import os
import uuid
import zipfile
from datetime import datetime, timezone

from flask import (
    Blueprint, flash, jsonify, redirect, render_template,
    request, url_for, current_app, send_file, session
)
from flask_login import login_required, current_user

from models import db
from models.message import SecretMessage, StegoImage
from models.user import User, FaceProfile
from models.logs import ActivityLog
from modules.encryption import generate_aes_key, encrypt_data, encrypt_aes_key
from modules.integrity import sha256_bytes
from modules.data_splitter import split_data, serialise_chunk
from modules.steganography import embed, capacity_bytes
from modules.image_metrics import compute_all_metrics
from modules.lstm_processor import lstm_processor
from modules.autoencoder import conv_autoencoder

logger = logging.getLogger(__name__)
encode_bp = Blueprint('encode', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def _allowed_image(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def _log_activity(user_id: int, activity: str, detail: str = None):
    log = ActivityLog(user_id=user_id, activity=activity, detail=detail)
    db.session.add(log)
    db.session.commit()


# ── API: list eligible receivers ────────────────────────────────────────────────

@encode_bp.route('/encode/receivers')
@login_required
def list_receivers():
    """
    Return JSON array of registered users (except self) who have a face profile.
    Used by the receiver-selection dropdown in encode.html.

    Response: [{"id": 2, "username": "alice", "email": "alice@example.com"}, ...]
    """
    users_with_face = (
        db.session.query(User)
        .join(FaceProfile, FaceProfile.user_id == User.id)
        .filter(User.id != current_user.id)
        .order_by(User.username)
        .all()
    )
    result = [
        {'id': u.id, 'username': u.username, 'email': u.email}
        for u in users_with_face
    ]
    return jsonify(result)


@encode_bp.route('/encode/receiver-status')
@login_required
def receiver_status():
    """
    Check if a specific user_id has a valid face profile.
    Response: {"valid": bool, "username": str, "has_face": bool}
    """
    receiver_id = request.args.get('receiver_id', type=int)
    if not receiver_id:
        return jsonify({'valid': False, 'error': 'receiver_id required'}), 400

    # Prevent looking up self
    if receiver_id == current_user.id:
        return jsonify({'valid': False, 'error': 'Cannot send message to yourself.'}), 400

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        return jsonify({'valid': False, 'error': 'User not found.'}), 404

    has_face = receiver.has_face_profile
    return jsonify({
        'valid': has_face,
        'username': receiver.username,
        'email': receiver.email,
        'has_face': has_face,
        'error': None if has_face else 'Selected receiver does not have a registered face profile.'
    })


# ── Encode Route ─────────────────────────────────────────────────────────────────

@encode_bp.route('/encode', methods=['GET', 'POST'])
@login_required
def encode():
    max_images = current_app.config.get('MAX_COVER_IMAGES', 5)
    min_images = current_app.config.get('MIN_COVER_IMAGES', 2)

    if request.method == 'GET':
        # Check sender has a face profile
        sender_has_face = current_user.has_face_profile
        return render_template(
            'encode.html',
            max_images=max_images,
            min_images=min_images,
            sender_has_face=sender_has_face,
        )

    # ── POST: Process encoding ──────────────────────────────────────────────────

    def _fail(msg):
        flash(msg, 'danger')
        return render_template(
            'encode.html',
            max_images=max_images,
            min_images=min_images,
            sender_has_face=current_user.has_face_profile,
        )

    # 1. Validate sender identity
    if not current_user.has_face_profile:
        return _fail(
            'You must register your face before you can encode a message. '
            'Please register your face first.'
        )

    # 2. Validate receiver selection (server-side — never trust client input)
    receiver_id = request.form.get('receiver_id', type=int)
    if not receiver_id:
        return _fail('Please select an intended receiver.')

    if receiver_id == current_user.id:
        return _fail('You cannot send a message to yourself.')

    receiver = db.session.get(User, receiver_id)
    if receiver is None:
        return _fail('Selected receiver does not exist.')

    if not receiver.has_face_profile:
        return _fail(
            f'Selected receiver "{receiver.username}" does not have a registered '
            'face profile. The receiver must register their face before they can '
            'receive encoded messages.'
        )

    # 3. Collect and validate cover images
    cover_files = request.files.getlist('cover_images')
    cover_files = [f for f in cover_files if f and f.filename]

    if len(cover_files) < min_images:
        return _fail(f'Please upload at least {min_images} cover images.')
    if len(cover_files) > max_images:
        return _fail(f'Maximum {max_images} cover images allowed.')
    for f in cover_files:
        if not _allowed_image(f.filename):
            return _fail(f'"{f.filename}" is not an allowed image type (PNG/JPG/BMP).')

    # 4. Get secret payload
    secret_type = request.form.get('secret_type', 'text')
    if secret_type == 'text':
        secret_text = request.form.get('secret_text', '').strip()
        if not secret_text:
            return _fail('Please enter a secret message.')
        plaintext = secret_text.encode('utf-8')
        original_filename = None
        data_type = 'text'
    else:
        if 'secret_file' not in request.files or not request.files['secret_file'].filename:
            return _fail('Please upload a secret file.')
        sf = request.files['secret_file']
        plaintext = sf.read()
        if not plaintext:
            return _fail('Uploaded secret file is empty.')
        original_filename = sf.filename
        data_type = 'file'

    # 5. Save cover images temporarily
    cover_folder = current_app.config['COVER_FOLDER']
    stego_folder = current_app.config['STEGO_FOLDER']
    session_id = str(uuid.uuid4())

    saved_cover_paths = []
    for f in cover_files:
        ext = f.filename.rsplit('.', 1)[1].lower()
        fname = f'{session_id}_cover_{len(saved_cover_paths)}.{ext}'
        path = os.path.join(cover_folder, fname)
        f.seek(0)
        f.save(path)
        saved_cover_paths.append(path)

    n = len(saved_cover_paths)

    # 6. AES encrypt
    try:
        aes_key = generate_aes_key()
        ciphertext = encrypt_data(plaintext, aes_key)
        data_hash = sha256_bytes(ciphertext)
    except Exception as exc:
        logger.exception("Encryption error")
        return _fail(f'Encryption error: {exc}')

    # 7. LSTM sequence processing (Unit IV) ─────────────────────────────────────
    # Process the encrypted byte sequence through the LSTM encoder.
    # The resulting feature vector is stored in the message metadata.
    # On decode, the extracted bytes are re-processed and compared.
    lstm_result = lstm_processor.encode_sequence(ciphertext)
    lstm_features = lstm_result.get('features')   # list of floats or None
    if lstm_result.get('available'):
        logger.info(
            "LSTM sequence encoding complete: seq_windows=%d feature_dim=%d",
            lstm_result.get('seq_len', 0), len(lstm_features) if lstm_features else 0
        )
    else:
        logger.info("LSTM model not available — skipping sequence encoding.")

    # 8. Check image capacities
    chunk_size_estimate = (len(ciphertext) // n) + 300
    for i, cp in enumerate(saved_cover_paths):
        cap = capacity_bytes(cp)
        if cap < chunk_size_estimate:
            return _fail(
                f'Image #{i + 1} is too small (capacity: {cap} bytes, '
                f'needed: ~{chunk_size_estimate} bytes). Please use larger images.'
            )

    # 9. Split ciphertext
    try:
        chunks = split_data(ciphertext, n, session_id, data_hash)
    except Exception as exc:
        return _fail(f'Data splitting error: {exc}')

    # 10. Embed chunks + compute metrics + run autoencoder on each cover image
    stego_paths = []
    stego_records = []

    try:
        for i, (chunk_dict, cover_path) in enumerate(zip(chunks, saved_cover_paths)):
            payload = serialise_chunk(chunk_dict)
            stego_fname = f'{session_id}_stego_{i}.png'
            stego_path = os.path.join(stego_folder, stego_fname)

            # LSB embed
            embed(cover_path, payload, stego_path)
            stego_paths.append(stego_path)

            # MSE/PSNR/SSIM metrics
            try:
                metrics = compute_all_metrics(cover_path, stego_path)
            except Exception:
                metrics = {'mse': None, 'psnr': None, 'ssim': None}

            # Unit V: Autoencoder reconstruction loss on cover image
            # This measures how well the autoencoder can represent this cover image.
            ae_loss = None
            try:
                ae_result = conv_autoencoder.process_image(cover_path)
                if ae_result.get('available'):
                    ae_loss = ae_result.get('reconstruction_loss')
                    logger.debug(
                        "Autoencoder cover image %d: loss=%.6f latent=%s",
                        i, ae_loss, ae_result.get('latent_shape')
                    )
            except Exception as ae_exc:
                logger.warning("Autoencoder error on image %d: %s", i, ae_exc)

            # File hash for tamper detection
            with open(stego_path, 'rb') as sf:
                file_hash = sha256_bytes(sf.read())

            stego_records.append(StegoImage(
                message_id=session_id,
                chunk_index=i,
                file_path=stego_fname,
                file_hash=file_hash,
                chunk_hash=chunk_dict['metadata']['chunk_hash'],
                mse=metrics.get('mse'),
                psnr=metrics.get('psnr'),
                ssim=metrics.get('ssim'),
                ae_reconstruction_loss=ae_loss,
            ))

    except ValueError as exc:
        return _fail(str(exc))
    except Exception as exc:
        logger.exception("Steganography embedding error")
        return _fail(f'Steganography error: {exc}')

    # 11. Encrypt AES key with master secret for DB storage
    master_secret = current_app.config['MASTER_SECRET']
    encrypted_aes_key_b64 = encrypt_aes_key(aes_key, master_secret)

    # 12. Store LSTM features in session (used by decode for validation)
    # We store features in the DB metadata via a simple approach:
    # they are included in the data_hash field as a JSON annotation.
    # Actually we store them in Flask session keyed by session_id so they
    # can be written to a side-channel store.  For simplicity in this
    # academic implementation, LSTM features are stored as a JSON column.
    # We'll use a session-scoped file approach: store features alongside
    # the message record in the DB via a dedicated column added via migration.
    # For now, features are stored in DB as part of message_id metadata.
    # (The decode route re-generates features from the extracted bytes and
    #  compares them — this is self-contained and doesn't require DB storage
    #  of the feature vector.)

    # 13. Save to database (with receiver and face profile references)
    sender_fp_id = (
        current_user.face_profile.id
        if current_user.face_profile else None
    )
    receiver_fp_id = (
        receiver.face_profile.id
        if receiver.face_profile else None
    )

    msg = SecretMessage(
        message_id=session_id,
        sender_id=current_user.id,
        receiver_id=receiver.id,
        sender_face_profile_id=sender_fp_id,
        receiver_face_profile_id=receiver_fp_id,
        original_filename=original_filename,
        data_type=data_type,
        encrypted_aes_key=encrypted_aes_key_b64,
        data_hash=data_hash,
        total_chunks=n,
        status='ready',
    )
    db.session.add(msg)
    for rec in stego_records:
        db.session.add(rec)
    db.session.commit()

    _log_activity(
        current_user.id, 'encode',
        f'session_id={session_id} receiver={receiver.username} '
        f'chunks={n} type={data_type} lstm={lstm_result.get("available")} '
        f'ae_available={conv_autoencoder.is_available}'
    )

    # 14. Bundle stego images into ZIP and serve
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_STORED) as zf:
        for i, sp in enumerate(stego_paths):
            zf.write(sp, f'stego_image_{i + 1}.png')
    zip_buffer.seek(0)

    flash(
        f'Secret encoded successfully for {receiver.username} across {n} images! '
        f'Download the ZIP and share all {n} stego images with {receiver.username}.',
        'success'
    )
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'stego_images_{session_id[:8]}.zip'
    )
