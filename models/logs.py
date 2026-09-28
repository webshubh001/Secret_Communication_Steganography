"""
models/logs.py — AuthenticationLog and ActivityLog database models.
"""

from datetime import datetime, timezone
from models import db


class AuthenticationLog(db.Model):
    """
    Records every authentication attempt (password login + face recognition).
    Used for security monitoring and dashboard statistics.
    """

    __tablename__ = 'authentication_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )

    # 'password' | 'face'
    authentication_type = db.Column(db.String(20), nullable=False)

    # 'success' | 'failure'
    status = db.Column(db.String(20), nullable=False)

    # Optional detail message (e.g. "No face detected", "Distance 0.72 > threshold")
    detail = db.Column(db.String(255), nullable=True)

    ip_address = db.Column(db.String(45), nullable=True)   # IPv4 or IPv6
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationship ────────────────────────────────────────────────────────────
    user = db.relationship('User', back_populates='auth_logs')

    def __repr__(self):
        return (
            f'<AuthLog user={self.user_id} type={self.authentication_type}'
            f' status={self.status}>'
        )


class ActivityLog(db.Model):
    """
    Records user activities such as encoding, decoding, and profile changes.
    Used for dashboard activity feed and audit trail.
    """

    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )

    # Short activity name, e.g. 'encode', 'decode', 'face_register'
    activity = db.Column(db.String(100), nullable=False)

    # Optional reference to a message_id
    related_message_id = db.Column(db.String(64), nullable=True)

    # Additional context as free text
    detail = db.Column(db.String(512), nullable=True)

    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationship ────────────────────────────────────────────────────────────
    user = db.relationship('User', back_populates='activity_logs')

    def __repr__(self):
        return f'<ActivityLog user={self.user_id} activity={self.activity}>'
