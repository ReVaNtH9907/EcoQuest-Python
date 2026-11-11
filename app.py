"""
EcoQuest — Application entry point.

Uses the Flask application factory pattern.
Configures database models, mail services, session lifecycle,
and template context providers.
"""

import os
from flask import Flask, render_template, session, g
from config import config_by_name
from models import db, User
from services.email_service import mail
from services.csrf import generate_csrf_token


def create_app(config_name=None):
    """
    Application factory.

    Args:
        config_name: One of 'development', 'production', or 'testing'.
                     Defaults to the FLASK_ENV environment variable,
                     falling back to 'development'.

    Returns:
        A configured Flask application instance.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_relative_config=True,
    )

    # Load configuration
    app.config.from_object(config_by_name[config_name])

    # Validate production SECRET_KEY security
    if config_name == "production" or os.environ.get("FLASK_ENV") == "production":
        # Always inspect current environment variable in production
        secret_key = os.environ.get("SECRET_KEY")
        insecure_keys = {
            "dev-secret-key-change-in-production",
            "replace-with-a-strong-random-key",
            "secret",
            "changeme",
            "ecoquest-dev-local-secret-key-3b7c89f0",
        }
        if not secret_key or secret_key.strip() in insecure_keys or len(secret_key.strip()) < 16:
            raise ValueError(
                "Insecure or missing SECRET_KEY in production environment. "
                "Set a strong SECRET_KEY (minimum 16 characters) via environment variables."
            )
        app.config["SECRET_KEY"] = secret_key

    # Ensure required directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    if "UPLOAD_FOLDER" in app.config:
        try:
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        except OSError:
            pass
    if "EVIDENCE_FOLDER" in app.config:
        try:
            os.makedirs(app.config["EVIDENCE_FOLDER"], exist_ok=True)
        except OSError:
            pass

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)

    # Setup database tables automatically
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass

        # Dialect-agnostic schema synchronization (works for SQLite and PostgreSQL)
        try:
            with db.engine.connect() as conn:
                from sqlalchemy import inspect, text
                inspector = inspect(db.engine)
                table_names = inspector.get_table_names()

                if "users" in table_names:
                    user_cols = [c["name"] for c in inspector.get_columns("users")]
                    if "total_xp" not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN total_xp INTEGER DEFAULT 0 NOT NULL"))
                        conn.commit()
                    if "is_admin" not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE NOT NULL"))
                        conn.commit()

                if "submissions" in table_names:
                    sub_cols = [c["name"] for c in inspector.get_columns("submissions")]
                    new_sub_cols = [
                        ("confidence_score", "FLOAT"),
                        ("evidence_relevance", "VARCHAR(50)"),
                        ("before_after_comparison", "TEXT"),
                        ("detected_inconsistencies", "TEXT"),
                        ("verification_explanation", "TEXT"),
                        ("ai_findings", "TEXT"),
                        ("review_decision", "VARCHAR(50)"),
                        ("reviewed_by", "VARCHAR(100)"),
                        ("reviewed_at", "TIMESTAMP"),
                        ("image_hash_before", "VARCHAR(64)"),
                        ("image_hash_after", "VARCHAR(64)"),
                        ("is_demo_verification", "BOOLEAN DEFAULT FALSE NOT NULL"),
                        ("admin_feedback", "TEXT"),
                        ("xp_awarded", "BOOLEAN DEFAULT FALSE NOT NULL"),
                        ("xp_awarded_amount", "INTEGER DEFAULT 0 NOT NULL"),
                    ]
                    for col_name, col_type in new_sub_cols:
                        if col_name not in sub_cols:
                            conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
        except Exception:
            pass

        # Seed learning curriculum if not already present
        try:
            from services.learning_service import seed_learning_curriculum
            seed_learning_curriculum(db.session)
        except Exception:
            pass

        # Seed environmental missions if not already present
        try:
            from services.mission_service import seed_missions
            seed_missions(db.session)
        except Exception:
            pass

        # Seed achievement badges if not already present
        try:
            from services.gamification_service import seed_badges
            seed_badges(db.session)
        except Exception:
            pass

    # Session authentication hook
    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.current_user = None
        else:
            g.current_user = db.session.get(User, user_id)

    # Context processors for Jinja2 templates
    @app.context_processor
    def inject_template_globals():
        return {
            "current_user": getattr(g, "current_user", None),
            "csrf_token": generate_csrf_token,
        }

    # Register all blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    return app


def _register_blueprints(app):
    """Register route blueprints with the application."""
    from routes import (
        main_bp,
        auth_bp,
        dashboard_bp,
        learning_bp,
        missions_bp,
        leaderboard_bp,
        profile_bp,
        admin_bp,
    )

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(learning_bp, url_prefix="/learning")
    app.register_blueprint(missions_bp, url_prefix="/missions")
    app.register_blueprint(leaderboard_bp, url_prefix="/leaderboard")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_error_handlers(app):
    """Register custom error pages."""

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template("errors/500.html"), 500


# WSGI application discovery for serverless / production servers (e.g. Vercel, Gunicorn)
app = None
try:
    app = create_app()
except ValueError:
    # Occurs if FLASK_ENV=production is set without SECRET_KEY during initial import
    pass


# --- Development server entry point ---
if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    application = create_app(env)

    # Enable debug mode only in development environment
    debug_mode = application.config.get("DEBUG", False) and (env == "development")

    application.run(
        host="127.0.0.1",
        port=5000,
        debug=debug_mode,
    )
