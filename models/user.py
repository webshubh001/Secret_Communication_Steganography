"""
models/user.py — User and FaceProfile database models.
"""

import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models import db


class User(UserMixin, db.Model):
    """
    Registered user account.
    Passwords are stored as bcrypt hashes via Werkzeug — never as plaintext.
    """

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────────────
    face_profile = db.relationship(
        'FaceProfile', back_populates='user',
        uselist=False, cascade='all, delete-orphan'
    )
    messages = db.relationship(
        'SecretMessage', back_populates='sender',
        foreign_keys='SecretMessage.sender_id',
        cascade='all, delete-orphan'
    )
    # v2: messages where this user is the intended receiver
    received_messages = db.relationship(
        'SecretMessage', back_populates='receiver',
        foreign_keys='SecretMessage.receiver_id',
        cascade='all, delete-orphan'
    )
    auth_logs = db.relationship(
        'AuthenticationLog', back_populates='user',
        cascade='all, delete-orphan'
    )
    activity_logs = db.relationship(
        'ActivityLog', back_populates='user',
        cascade='all, delete-orphan'
    )


    # ── Password helpers ────────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        """Hash and store the user password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def has_face_profile(self) -> bool:
        """True if this user has registered a face embedding."""
        return self.face_profile is not None

    def __repr__(self):
        return f'<User {self.username}>'


class FaceProfile(db.Model):
    """
    Stores the 128-dimensional face embedding for a user.
    The embedding is serialised as a JSON array.
    Raw face images are NOT stored — only the numerical embedding.
    """

    __tablename__ = 'face_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True
    )
    # JSON-serialised list of 128 floats (face_recognition encoding)
    face_embedding = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationship ────────────────────────────────────────────────────────────
    user = db.relationship('User', back_populates='face_profile')

    # ── Embedding helpers ───────────────────────────────────────────────────────
    def set_embedding(self, embedding: list) -> None:
        """Serialise and store the face embedding."""
        self.face_embedding = json.dumps([float(x) for x in embedding])

    def get_embedding(self) -> list:
        """Deserialise and return the face embedding as a Python list."""
        return json.loads(self.face_embedding)

    def __repr__(self):
        return f'<FaceProfile user_id={self.user_id}>'
