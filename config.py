"""
config.py — Central configuration module for the Secret Communication System.
All sensitive values are loaded from environment variables via .env file.
Never hard-code secrets in this file.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (development only)
load_dotenv()


class Config:
    """Base configuration class."""

    # ─── Flask Core ────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    DEBUG = False
    TESTING = False

    # ─── Database ──────────────────────────────────────────────────────────────
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_DIR = os.path.join(BASE_DIR, 'database')
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or f'sqlite:///{os.path.join(DB_DIR, "app.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── File Uploads ──────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB hard limit
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    COVER_FOLDER = os.path.join(UPLOAD_FOLDER, 'covers')
    STEGO_FOLDER = os.path.join(UPLOAD_FOLDER, 'stego')
    EXTRACTED_FOLDER = os.path.join(UPLOAD_FOLDER, 'extracted')

    # Allowed image extensions for cover images
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
    # Allowed face image extensions
    ALLOWED_FACE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    # Maximum number of cover images allowed per encoding session
    MAX_COVER_IMAGES = 5
    MIN_COVER_IMAGES = 2

    # ─── Steganography ─────────────────────────────────────────────────────────
    # Number of LSBs used per colour channel (1 = minimal distortion)
    LSB_BITS = 1

    # ─── Encryption ────────────────────────────────────────────────────────────
    # Master secret used to protect per-session AES keys stored in the DB.
    # MUST be set via environment variable in production.
    MASTER_SECRET = os.environ.get('MASTER_SECRET') or 'CHANGE_THIS_MASTER_SECRET_IN_ENV'
    AES_KEY_SIZE = 32   # 256-bit AES key

    # ─── Face Recognition ──────────────────────────────────────────────────────
    # Euclidean distance threshold for face_recognition library.
    # Lower = stricter. Default 0.6 works well for most cases.
    FACE_RECOGNITION_THRESHOLD = float(
        os.environ.get('FACE_RECOGNITION_THRESHOLD', '0.6')
    )
    # Number of face samples required during registration
    MIN_FACE_SAMPLES = 1

    # ─── Rate Limiting ─────────────────────────────────────────────────────────
    RATELIMIT_LOGIN = '10 per minute'
    RATELIMIT_FACE_AUTH = '5 per minute'
    RATELIMIT_REGISTER = '5 per minute'

    # ─── Session Security ──────────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour


class DevelopmentConfig(Config):
    """Development configuration — verbose errors, debug mode."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration — strict security."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Requires HTTPS


# ─── Config selector ───────────────────────────────────────────────────────────
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    return config_map.get(env, config_map['default'])
