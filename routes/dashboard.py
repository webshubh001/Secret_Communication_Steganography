"""
routes/dashboard.py — Dashboard, history, and profile routes.
"""

import os
from datetime import datetime, timezone

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, current_app
)
from flask_login import login_required, current_user

from models import db
from models.message import SecretMessage
from models.logs import AuthenticationLog, ActivityLog

dashboard_bp = Blueprint('dashboard', __name__)


# ─── Dashboard ──────────────────────────────────────────────────────────────────

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    # Summary statistics
    total_encoded = SecretMessage.query.filter_by(
        sender_id=current_user.id
    ).count()

    total_decoded = SecretMessage.query.filter_by(
        sender_id=current_user.id, status='decoded'
    ).count()

    face_auth_success = AuthenticationLog.query.filter_by(
        user_id=current_user.id,
        authentication_type='face',
        status='success'
    ).count()

    face_auth_fail = AuthenticationLog.query.filter_by(
        user_id=current_user.id,
        authentication_type='face',
        status='failure'
    ).count()

    # Recent messages
    recent_messages = (
        SecretMessage.query
        .filter_by(sender_id=current_user.id)
        .order_by(SecretMessage.created_at.desc())
        .limit(5)
        .all()
    )

    # Recent activity
    recent_activity = (
        ActivityLog.query
        .filter_by(user_id=current_user.id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(10)
        .all()
    )

    return render_template(
        'dashboard.html',
        total_encoded=total_encoded,
        total_decoded=total_decoded,
        face_auth_success=face_auth_success,
        face_auth_fail=face_auth_fail,
        recent_messages=recent_messages,
        recent_activity=recent_activity,
    )


# ─── History ────────────────────────────────────────────────────────────────────

@dashboard_bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    messages = (
        SecretMessage.query
        .filter_by(sender_id=current_user.id)
        .order_by(SecretMessage.created_at.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )

    auth_logs = (
        AuthenticationLog.query
        .filter_by(user_id=current_user.id)
        .order_by(AuthenticationLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return render_template('history.html',
                           messages=messages,
                           auth_logs=auth_logs)


# ─── Profile ────────────────────────────────────────────────────────────────────

@dashboard_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password changed successfully.', 'success')

        elif action == 'update_email':
            new_email = request.form.get('email', '').strip().lower()
            from models.user import User
            existing = User.query.filter_by(email=new_email).first()
            if '@' not in new_email:
                flash('Please enter a valid email address.', 'danger')
            elif existing and existing.id != current_user.id:
                flash('That email is already in use.', 'danger')
            else:
                current_user.email = new_email
                db.session.commit()
                flash('Email updated successfully.', 'success')

        return redirect(url_for('dashboard.profile'))

    return render_template('profile.html')
