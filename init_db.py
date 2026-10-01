"""
init_db.py — Database initialisation and migration script.

Fresh install:
    python init_db.py

Existing database (adds v2 columns without data loss):
    python init_db.py

The script uses SQLAlchemy's create_all() (idempotent for new tables) and then
runs ALTER TABLE statements via SQLite for the new v2 columns, ignoring errors
when columns already exist (SQLite does not support IF NOT EXISTS for columns).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db


def _add_column_if_missing(connection, table: str, column: str, col_type: str):
    """
    Attempt to add a column to a SQLite table.
    Silently ignores 'duplicate column name' errors (column already exists).
    """
    from sqlalchemy import text
    try:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        )
        print(f"  [+] Added column {table}.{column}")
    except Exception as exc:
        if 'duplicate column name' in str(exc).lower():
            print(f"  [=] Column {table}.{column} already exists - skipped.")
        else:
            print(f"  [!] Could not add {table}.{column}: {exc}")



def init_database():
    """Create all database tables and migrate existing ones."""
    app = create_app()

    with app.app_context():
        print("[DB]  Initialising / migrating database...")

        # Import all models so SQLAlchemy registers them before create_all()
        from models.user import User, FaceProfile          # noqa: F401
        from models.message import SecretMessage, StegoImage  # noqa: F401
        from models.logs import AuthenticationLog, ActivityLog  # noqa: F401

        # Create any missing tables (idempotent)
        db.create_all()
        print("[OK]  Tables created / verified.")

        # ── v2 migration: add new columns to existing tables ──────────────────
        print("\n[MIGRATE]  Running v2 column migrations...")
        with db.engine.connect() as conn:
            # secret_messages: receiver and face profile references
            _add_column_if_missing(
                conn, 'secret_messages', 'receiver_id', 'INTEGER REFERENCES users(id)'
            )
            _add_column_if_missing(
                conn, 'secret_messages', 'sender_face_profile_id',
                'INTEGER REFERENCES face_profiles(id)'
            )
            _add_column_if_missing(
                conn, 'secret_messages', 'receiver_face_profile_id',
                'INTEGER REFERENCES face_profiles(id)'
            )
            # stego_images: autoencoder reconstruction loss
            _add_column_if_missing(
                conn, 'stego_images', 'ae_reconstruction_loss', 'REAL'
            )
            conn.commit()

        # Verify tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\n[TABLES]  Present: {', '.join(tables)}")

        # Verify new columns in secret_messages
        cols = {c['name'] for c in inspector.get_columns('secret_messages')}
        required_v2 = {'receiver_id', 'sender_face_profile_id', 'receiver_face_profile_id'}
        if required_v2.issubset(cols):
            print("[OK]  v2 columns verified in secret_messages.")
        else:
            print(f"[WARN]  Missing v2 columns: {required_v2 - cols}")

        print("\n[DONE]  Database ready! Run:  python app.py")


if __name__ == '__main__':
    init_database()

