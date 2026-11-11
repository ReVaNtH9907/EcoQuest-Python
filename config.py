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


def normalize_database_url(url: str | None) -> str:
    """
    Ensure the database connection URI uses SQLAlchemy-compatible scheme.
    Converts legacy 'postgres://' prefixes to 'postgresql://',
    preserves existing valid URIs, and provides local SQLite fallback.
    """
    if not url or not url.strip():
        if os.environ.get("VERCEL"):
            return "sqlite:////tmp/ecoquest.db"
        default_db_path = os.path.join(BASE_DIR, "instance", "ecoquest.db")
        return f"sqlite:///{default_db_path}"

    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://"):]
    return cleaned


class Config:
    """Base configuration shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # SQLAlchemy database configuration with Supabase / PostgreSQL support and SQLite fallback
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Uploads & Evidence configuration
    if os.environ.get("VERCEL"):
        UPLOAD_FOLDER = "/tmp/uploads/profiles"
        EVIDENCE_FOLDER = "/tmp/evidence"
    else:
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

    # Supabase configuration (PostgreSQL & Storage)
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_PROFILES_BUCKET = os.environ.get("SUPABASE_STORAGE_PROFILES_BUCKET", "profile-pictures")
    SUPABASE_STORAGE_EVIDENCE_BUCKET = os.environ.get("SUPABASE_STORAGE_EVIDENCE_BUCKET", "mission-evidence")

    # AI verification service
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
    SECRET_KEY = os.environ.get("SECRET_KEY")


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
