"""
extensions.py — Shared Flask extension instances.
Separating these from app.py breaks the circular import that occurs
when route blueprints try to import `limiter` from `app`.
"""

from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

login_manager = LoginManager()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",   # explicit in-memory storage (dev-only)
)
