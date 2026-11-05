import os
import secrets
from datetime import datetime

from flask import Flask, session

from courier_service_backend.config import Config
from courier_service_backend.extensions import db, login_manager, socketio
from courier_service_backend.models import Admin, Customer
from courier_service_backend.routes import admin_bp, api_bp, web_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = None
    socketio.init_app(app, cors_allowed_origins=app.config["CORS_ALLOWED_ORIGINS"])

    @login_manager.user_loader
    def load_user(user_id):
        if user_id.startswith("admin:"):
            admin_id = user_id.removeprefix("admin:")
            return db.session.get(Admin, int(admin_id)) if admin_id.isdecimal() else None
        return db.session.get(Customer, int(user_id)) if user_id.isdecimal() else None

    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(web_bp)

    @app.context_processor
    def inject_template_globals():
        def csrf_token():
            token = session.get("_csrf_token")
            if token is None:
                token = secrets.token_urlsafe(32)
                session["_csrf_token"] = token
            return token

        def static_version(filename):
            return os.stat(os.path.join(app.static_folder, filename)).st_mtime_ns

        return {
            "current_year": datetime.now().year,
            "csrf_token": csrf_token,
            "static_version": static_version,
        }

    with app.app_context():
        db.create_all()
        _provision_admin()

    return app


def _provision_admin():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email and not password:
        return
    if not email or len(password) < 12:
        raise RuntimeError(
            "Set both ADMIN_EMAIL and an ADMIN_PASSWORD of at least 12 characters."
        )
    if Admin.query.filter_by(email=email).first():
        return

    admin = Admin(email=email)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
