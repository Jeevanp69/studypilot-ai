"""
App factory. Wires together the Flask app, database, login manager,
and rate limiter, then registers the two blueprints (auth, main).

Kept as a factory (create_app) rather than a bare module-level app
so tests and different configs can spin up separate instances later.
"""

import os
from flask import Flask, app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

load_dotenv()

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(__name__)

    secret_key = os.environ.get("SECRET_KEY")

    if not secret_key:
        if app.debug:
            secret_key = "dev-only-secret-key-change-me"
        else:
            raise RuntimeError(
                "SECRET_KEY must be configured in production."
            )

    app.config["SECRET_KEY"] = secret_key
    # Defaults to a local SQLite file so you can run this with zero setup.
    # On deployment, set DATABASE_URL to your managed Postgres URL instead.
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url:
        database_url = "sqlite:///local.db"

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB upload cap
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    limiter.init_app(app)
    

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth import auth_bp
    from app.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()

    return app
