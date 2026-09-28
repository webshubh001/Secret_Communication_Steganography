"""
models/__init__.py — SQLAlchemy db instance shared across all models.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
