"""
init_db.py — Database initialization script.
Run once before starting the application for the first time:
    python init_db.py
"""

import os
import sys

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db


def init_database():
    """Create all database tables and required directories."""
    app = create_app()

    with app.app_context():
        print("🗄️  Initialising database...")

        # Import all models so SQLAlchemy registers them before create_all()
        from models.user import User, FaceProfile      # noqa: F401
        from models.message import SecretMessage, StegoImage  # noqa: F401
        from models.logs import AuthenticationLog, ActivityLog  # noqa: F401

        db.create_all()
        print("✅  All tables created successfully.")

        # Verify tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📋  Tables present: {', '.join(tables)}")

        print("\n🎉  Database initialised! You can now run: python app.py")


if __name__ == '__main__':
    init_database()
