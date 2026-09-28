"""
models/message.py — SecretMessage and StegoImage database models.
"""

from datetime import datetime, timezone
from models import db


class SecretMessage(db.Model):
    """
    Represents a single encoding session.
    Links the sender, the AES key (encrypted), and all generated stego images.
    """

    __tablename__ = 'secret_messages'

    id = db.Column(db.Integer, primary_key=True)

    # UUID string — also embedded in every stego image for reconstruction
    message_id = db.Column(db.String(64), unique=True, nullable=False, index=True)

    sender_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )

    # Optional: original filename if the secret was a file upload
    original_filename = db.Column(db.String(255), nullable=True)

    # 'text' or 'file'
    data_type = db.Column(db.String(10), nullable=False, default='text')

    # AES key encrypted with the master secret (safe to store in DB)
    encrypted_aes_key = db.Column(db.Text, nullable=False)

    # SHA-256 hex digest of the complete encrypted ciphertext
    data_hash = db.Column(db.String(64), nullable=False)

    total_chunks = db.Column(db.Integer, nullable=False)

    # 'pending' | 'ready' | 'decoded' | 'failed'
    status = db.Column(db.String(20), nullable=False, default='pending')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    decoded_at = db.Column(db.DateTime, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────────────
    sender = db.relationship(
        'User', back_populates='messages', foreign_keys=[sender_id]
    )
    stego_images = db.relationship(
        'StegoImage', back_populates='message',
        cascade='all, delete-orphan',
        order_by='StegoImage.chunk_index'
    )

    def __repr__(self):
        return f'<SecretMessage {self.message_id[:8]}... chunks={self.total_chunks}>'


class StegoImage(db.Model):
    """
    Represents one stego image (one chunk of the encrypted data).
    Each stego image embeds exactly one chunk of the split ciphertext.
    """

    __tablename__ = 'stego_images'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.String(64), db.ForeignKey('secret_messages.message_id'), nullable=False
    )
    chunk_index = db.Column(db.Integer, nullable=False)   # 0-based

    # Path relative to STEGO_FOLDER (stored without the absolute prefix
    # to remain portable if the upload folder is moved)
    file_path = db.Column(db.String(512), nullable=False)

    # SHA-256 of the stego image file itself (for tamper detection)
    file_hash = db.Column(db.String(64), nullable=False)

    # SHA-256 of the embedded chunk bytes (for chunk-level integrity)
    chunk_hash = db.Column(db.String(64), nullable=False)

    # Image quality metrics compared to the original cover image
    mse = db.Column(db.Float, nullable=True)
    psnr = db.Column(db.Float, nullable=True)
    ssim = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationship ────────────────────────────────────────────────────────────
    message = db.relationship('SecretMessage', back_populates='stego_images')

    def __repr__(self):
        return (
            f'<StegoImage chunk={self.chunk_index}/{self.message.total_chunks - 1}>'
        )
