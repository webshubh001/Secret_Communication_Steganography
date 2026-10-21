"""
app.py — Flask application factory.
Entry point for the Secret Communication System.
"""

import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import get_config
from models import db
from models.user import User
from extensions import login_manager, limiter


def create_app(config_class=None):
    """Application factory — creates and configures the Flask application."""

    app = Flask(__name__)

    # ── Load configuration ─────────────────────────────────────────────────────
    cfg = config_class or get_config()
    app.config.from_object(cfg)

    # ── Ensure required upload directories exist ───────────────────────────────
    for folder in [
        app.config['COVER_FOLDER'],
        app.config['STEGO_FOLDER'],
        app.config['EXTRACTED_FOLDER'],
        app.config['DB_DIR'],
    ]:
        os.makedirs(folder, exist_ok=True)

    # ── Initialise extensions ──────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # ── Register blueprints ────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.face import face_bp
    from routes.encode import encode_bp
    from routes.decode import decode_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(face_bp, url_prefix='/face')
    app.register_blueprint(encode_bp)
    app.register_blueprint(decode_bp)
    app.register_blueprint(dashboard_bp)

    # ── User loader for Flask-Login ────────────────────────────────────────────
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('errors/413.html'), 413

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # ── Landing page route ─────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('index.html')

    return app


# ─── Application instance ──────────────────────────────────────────────────────
app = create_app()

if __name__ == '__main__':
    # Disable the hot-reloader because TensorFlow modifies its own files on load,
    # which triggers Werkzeug to abruptly restart the server and kill the request.
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
