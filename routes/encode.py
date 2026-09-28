"""
routes/encode.py — Multi-image LSB steganography encoding route.

Full pipeline:
  1. Validate uploaded cover images
  2. Generate AES-256 session key
  3. Encrypt the secret (text or file) with AES-256-CBC
  4. Compute SHA-256 integrity hash
  5. Split ciphertext into N chunks (one per cover image)
  6. Embed each chunk into its cover image (LSB)
  7. Compute image quality metrics (MSE, PSNR, SSIM)
  8. Store SecretMessage + StegoImage records in DB
  9. Serve stego images as a ZIP download
"""

import os
import uuid
import logging
import zipfile
import io
from datetime import datetime, timezone

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app, send_file, session
)
from flask_login import login_required, current_user

from models import db
from models.message import SecretMessage, StegoImage
from models.logs import ActivityLog
from modules.encryption import generate_aes_key, encrypt_data, encrypt_aes_key
from modules.integrity import sha256_bytes
from modules.data_splitter import split_data, serialise_chunk
from modules.steganography import embed, capacity_bytes
from modules.image_metrics import compute_all_metrics

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


# ─── Encode Route ───────────────────────────────────────────────────────────────

@encode_bp.route('/encode', methods=['GET', 'POST'])
@login_required
def encode():
    if request.method == 'GET':
        max_images = current_app.config.get('MAX_COVER_IMAGES', 5)
        min_images = current_app.config.get('MIN_COVER_IMAGES', 2)
        return render_template('encode.html',
                               max_images=max_images,
                               min_images=min_images)

    # ── POST: Process encoding ─────────────────────────────────────────────────
    max_images = current_app.config.get('MAX_COVER_IMAGES', 5)
    min_images = current_app.config.get('MIN_COVER_IMAGES', 2)

    # 1. Collect and validate cover images
    cover_files = request.files.getlist('cover_images')
    cover_files = [f for f in cover_files if f and f.filename]

    if len(cover_files) < min_images:
        flash(f'Please upload at least {min_images} cover images.', 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)

    if len(cover_files) > max_images:
        flash(f'Maximum {max_images} cover images allowed.', 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)

    for f in cover_files:
        if not _allowed_image(f.filename):
            flash(f'"{f.filename}" is not an allowed image type (PNG/JPG/BMP only).', 'danger')
            return render_template('encode.html',
                                   max_images=max_images, min_images=min_images)

    # 2. Get secret payload
    secret_type = request.form.get('secret_type', 'text')
    if secret_type == 'text':
        secret_text = request.form.get('secret_text', '').strip()
        if not secret_text:
            flash('Please enter a secret message.', 'danger')
            return render_template('encode.html',
                                   max_images=max_images, min_images=min_images)
        plaintext = secret_text.encode('utf-8')
        original_filename = None
        data_type = 'text'
    else:
        if 'secret_file' not in request.files or not request.files['secret_file'].filename:
            flash('Please upload a secret file.', 'danger')
            return render_template('encode.html',
                                   max_images=max_images, min_images=min_images)
        sf = request.files['secret_file']
        plaintext = sf.read()
        if not plaintext:
            flash('Uploaded secret file is empty.', 'danger')
            return render_template('encode.html',
                                   max_images=max_images, min_images=min_images)
        original_filename = sf.filename
        data_type = 'file'

    # 3. Save cover images temporarily
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

    # 4. Check capacity for each cover image
    try:
        aes_key = generate_aes_key()
        ciphertext = encrypt_data(plaintext, aes_key)
        data_hash = sha256_bytes(ciphertext)

        # Estimate: each chunk is roughly len(ciphertext)/n bytes + ~200 bytes metadata
        chunk_size_estimate = (len(ciphertext) // n) + 300
        for i, cp in enumerate(saved_cover_paths):
            cap = capacity_bytes(cp)
            if cap < chunk_size_estimate:
                flash(
                    f'Image #{i + 1} is too small to hold its data chunk '
                    f'(capacity: {cap} bytes, needed: ~{chunk_size_estimate} bytes). '
                    f'Please use larger images.',
                    'danger'
                )
                return render_template('encode.html',
                                       max_images=max_images, min_images=min_images)
    except Exception as exc:
        logger.exception("Encryption error")
        flash(f'Encryption error: {exc}', 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)

    # 5. Split ciphertext into chunks
    try:
        chunks = split_data(ciphertext, n, session_id, data_hash)
    except Exception as exc:
        flash(f'Data splitting error: {exc}', 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)

    # 6. Embed each chunk into its cover image and compute metrics
    stego_paths = []
    stego_records = []

    try:
        for i, (chunk_dict, cover_path) in enumerate(zip(chunks, saved_cover_paths)):
            payload = serialise_chunk(chunk_dict)
            stego_fname = f'{session_id}_stego_{i}.png'
            stego_path = os.path.join(stego_folder, stego_fname)

            embed(cover_path, payload, stego_path)
            stego_paths.append(stego_path)

            # Compute quality metrics
            try:
                metrics = compute_all_metrics(cover_path, stego_path)
            except Exception:
                metrics = {'mse': None, 'psnr': None, 'ssim': None}

            # Hash the stego image file for tamper detection
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
            ))
    except ValueError as exc:
        flash(str(exc), 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)
    except Exception as exc:
        logger.exception("Steganography embedding error")
        flash(f'Steganography error: {exc}', 'danger')
        return render_template('encode.html',
                               max_images=max_images, min_images=min_images)

    # 7. Encrypt AES key with master secret for DB storage
    master_secret = current_app.config['MASTER_SECRET']
    encrypted_aes_key_b64 = encrypt_aes_key(aes_key, master_secret)

    # 8. Save to database
    msg = SecretMessage(
        message_id=session_id,
        sender_id=current_user.id,
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

    _log_activity(current_user.id, 'encode',
                  f'session_id={session_id} chunks={n} type={data_type}')

    # 9. Bundle stego images into a ZIP and serve
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, sp in enumerate(stego_paths):
            zf.write(sp, f'stego_image_{i + 1}.png')
    zip_buffer.seek(0)

    flash(
        f'Secret encoded successfully across {n} images! '
        f'Download the ZIP and share all {n} stego images with the recipient.',
        'success'
    )
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'stego_images_{session_id[:8]}.zip'
    )
