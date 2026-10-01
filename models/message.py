"""
models/message.py — SecretMessage and StegoImage database models.

v2 Changes:
  - receiver_id FK → users.id  (nullable — backward compatible)
  - sender_face_profile_id FK → face_profiles.id  (nullable)
  - receiver_face_profile_id FK → face_profiles.id  (nullable)
  - is_legacy property to detect pre-v2 messages
  - ae_reconstruction_loss on StegoImage (nullable)
"""

from datetime import datetime, timezone
from models import db


class SecretMessage(db.Model):
    """
    Represents a single encoding session.
    Links the sender, optional receiver, encrypted AES key, and stego images.

    For v2+ messages:
      • receiver_id              — intended recipient user
      • sender_face_profile_id  — snapshot reference of sender's face profile
      • receiver_face_profile_id — snapshot reference of receiver's face profile
    Legacy messages (created before v2) have all three as NULL.
    """

    __tablename__ = 'secret_messages'

    id = db.Column(db.Integer, primary_key=True)

    # UUID string — also embedded in every stego image for reconstruction
    message_id = db.Column(db.String(64), unique=True, nullable=False, index=True)

    sender_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )

    # ── v2: receiver ────────────────────────────────────────────────────────────
    receiver_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True
    )

    # ── v2: face profile references at the time of encoding ────────────────────
    # These are foreign keys to FaceProfile.id, NOT raw embeddings.
    # If the face profile is later deleted, set NULL (no cascade delete).
    sender_face_profile_id = db.Column(
        db.Integer, db.ForeignKey('face_profiles.id', ondelete='SET NULL'),
        nullable=True
    )
    receiver_face_profile_id = db.Column(
        db.Integer, db.ForeignKey('face_profiles.id', ondelete='SET NULL'),
        nullable=True
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
    receiver = db.relationship(
        'User', back_populates='received_messages', foreign_keys=[receiver_id]
    )
    # Read-only face profile refs — do NOT cascade delete on these
    sender_face_profile_ref = db.relationship(
        'FaceProfile', foreign_keys=[sender_face_profile_id], passive_deletes=True
    )
    receiver_face_profile_ref = db.relationship(
        'FaceProfile', foreign_keys=[receiver_face_profile_id], passive_deletes=True
    )
    stego_images = db.relationship(
        'StegoImage', back_populates='message',
        cascade='all, delete-orphan',
        order_by='StegoImage.chunk_index'
    )

    # ── Helpers ─────────────────────────────────────────────────────────────────
    @property
    def is_legacy(self) -> bool:
        """True if this message predates the v2 sender/receiver face-auth feature."""
        return self.receiver_id is None

    def __repr__(self):
        return f'<SecretMessage {self.message_id[:8]}... chunks={self.total_chunks}>'


class StegoImage(db.Model):
    """
    Represents one stego image (one chunk of the encrypted data).
    """

    __tablename__ = 'stego_images'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.String(64), db.ForeignKey('secret_messages.message_id'), nullable=False
    )
    chunk_index = db.Column(db.Integer, nullable=False)   # 0-based

    file_path = db.Column(db.String(512), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    chunk_hash = db.Column(db.String(64), nullable=False)

    # LSB image quality metrics
    mse = db.Column(db.Float, nullable=True)
    psnr = db.Column(db.Float, nullable=True)
    ssim = db.Column(db.Float, nullable=True)

    # v2: Autoencoder reconstruction loss (nullable for legacy images)
    ae_reconstruction_loss = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    message = db.relationship('SecretMessage', back_populates='stego_images')

    def __repr__(self):
        return (
            f'<StegoImage chunk={self.chunk_index}/{self.message.total_chunks - 1}>'
        )

