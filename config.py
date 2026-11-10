"""
Application configuration classes.

Separates development and production settings.
Sensitive values are loaded from environment variables.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # SQLite for local development (will be replaced by Supabase PostgreSQL)
    default_db_path = os.path.join(BASE_DIR, "instance", "ecoquest.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{default_db_path}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "profiles")
    EVIDENCE_FOLDER = os.path.join(BASE_DIR, "instance", "evidence")
    MAX_CONTENT_LENGTH = 35 * 1024 * 1024  # 35 MB max request
    MAX_EVIDENCE_SIZE = 25 * 1024 * 1024   # 25 MB max per evidence item
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    ALLOWED_EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "webm", "mp4"}

    # Session configuration
    PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Mail configuration (for email OTP)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@ecoquest.org")

    # --- Future Supabase configuration (do not connect yet) ---
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # --- Future AI verification service ---
    AI_SERVICE_API_KEY = os.environ.get("AI_SERVICE_API_KEY", "")

    # Application settings
    APP_NAME = "EcoQuest"
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production-specific configuration."""

    DEBUG = False
    TESTING = False

    # In production, SECRET_KEY must be set via environment variable
    @property
    def SECRET_KEY(self):
        key = os.environ.get("SECRET_KEY")
        if not key:
            raise ValueError("SECRET_KEY environment variable is not set for production.")
        return key


class TestingConfig(Config):
    """Testing-specific configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Map environment names to configuration classes
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
