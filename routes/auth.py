"""
routes/auth.py — Authentication routes: register, login, logout.

Security measures implemented:
  • Password never stored as plaintext (Werkzeug pbkdf2 hashing).
  • Rate limiting on login and register endpoints.
  • CSRF protection via Flask-WTF (WTF_CSRF_ENABLED = True by default).
  • Input validation for all fields.
  • Secure session via Flask-Login.
"""

from datetime import datetime, timezone

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app
)
from flask_login import login_user, logout_user, login_required, current_user

from models import db
from models.user import User
from models.logs import AuthenticationLog, ActivityLog
from extensions import limiter

auth_bp = Blueprint('auth', __name__)


def _log_auth(user_id: int, auth_type: str, status: str, detail: str = None):
    """Helper to record an authentication event."""
    log = AuthenticationLog(
        user_id=user_id,
        authentication_type=auth_type,
        status=status,
        detail=detail,
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()


def _log_activity(user_id: int, activity: str, detail: str = None):
    """Helper to record a user activity."""
    log = ActivityLog(user_id=user_id, activity=activity, detail=detail)
    db.session.add(log)
    db.session.commit()


# ─── Registration ───────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # ── Validation ─────────────────────────────────────────────────────────
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if len(username) > 80:
            errors.append("Username must be 80 characters or fewer.")
        if not email or '@' not in email:
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            # Check uniqueness
            if User.query.filter_by(username=username).first():
                errors.append("Username is already taken.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with this email already exists.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html',
                                   username=username, email=email)

        # ── Create user ────────────────────────────────────────────────────────
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        _log_activity(user.id, 'register', f"New account: {username}")
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


# ─── Login ──────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        # Look up by username or email
        user = (
            User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier.lower()).first()
        )

        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            _log_auth(user.id, 'password', 'success')
            _log_activity(user.id, 'login', f"IP: {request.remote_addr}")
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.dashboard'))
        else:
            if user:
                _log_auth(user.id, 'password', 'failure', 'Wrong password')
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html')


# ─── Logout ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    _log_activity(current_user.id, 'logout')
    logout_user()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))
