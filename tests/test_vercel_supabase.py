"""
Unit and Integration Tests for Vercel & Supabase Production Readiness.

Validates:
1. Database URL normalization (converting postgres:// to postgresql:// and SQLite fallback).
2. PostgreSQL DDL compilation for all SQLAlchemy models via psycopg2 dialect.
3. Production SECRET_KEY enforcement (rejecting insecure placeholders or missing keys).
4. Safe dialect-agnostic database inspection and migration logic.
5. Supabase Storage abstraction (profiles and evidence buckets with graceful fallback).
6. Security checks ensuring service role credentials are never leaked.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from config import normalize_database_url, Config, ProductionConfig
from app import create_app
from models import (
    db,
    User,
    OTPVerification,
    LessonCategory,
    Lesson,
    QuizQuestion,
    QuizOption,
    LessonProgress,
    QuizAttempt,
    Mission,
    UserMission,
    Submission,
    XPTransaction,
    Badge,
    UserBadge,
    UserStreak,
)
from services.supabase_storage import (
    is_supabase_storage_enabled,
    upload_profile_picture_to_supabase,
    download_profile_picture_from_supabase,
    upload_evidence_to_supabase,
    download_evidence_from_supabase,
)


# --- 1. Database URL Normalization Tests ---

def test_normalize_database_url_converts_postgres_to_postgresql():
    """Ensure postgres:// is safely converted to postgresql+psycopg2://."""
    raw = "postgres://postgres:secretpassword@db.supabase.co:5432/postgres"
    expected = "postgresql+psycopg2://postgres:secretpassword@db.supabase.co:5432/postgres"
    assert normalize_database_url(raw) == expected


def test_normalize_database_url_preserves_postgresql():
    """Ensure driverless postgresql:// URLs get explicit psycopg2 driver."""
    raw = "postgresql://postgres:secretpassword@db.supabase.co:5432/postgres"
    expected = "postgresql+psycopg2://postgres:secretpassword@db.supabase.co:5432/postgres"
    assert normalize_database_url(raw) == expected


def test_normalize_database_url_fallback_to_sqlite():
    """Ensure empty or None database URL falls back cleanly to local SQLite."""
    assert "sqlite:///" in normalize_database_url(None)
    assert "sqlite:///" in normalize_database_url("")
    assert "sqlite:///" in normalize_database_url("   ")


def test_normalize_database_url_vercel_tmp_fallback(monkeypatch):
    """When running on Vercel with no DATABASE_URL, fallback to /tmp/ecoquest.db."""
    monkeypatch.setenv("VERCEL", "1")
    url = normalize_database_url("")
    assert url == "sqlite:////tmp/ecoquest.db"


# --- 2. PostgreSQL DDL Compilation Tests for All Models ---

@pytest.mark.parametrize(
    "model_cls",
    [
        User,
        OTPVerification,
        LessonCategory,
        Lesson,
        QuizQuestion,
        QuizOption,
        LessonProgress,
        QuizAttempt,
        Mission,
        UserMission,
        Submission,
        XPTransaction,
        Badge,
        UserBadge,
        UserStreak,
    ],
)
def test_all_models_compile_for_postgresql(model_cls):
    """Verify that every database model compiles valid DDL for PostgreSQL (psycopg2)."""
    ddl = str(CreateTable(model_cls.__table__).compile(dialect=postgresql.dialect()))
    assert "CREATE TABLE" in ddl
    assert model_cls.__tablename__ in ddl


# --- 3. Production SECRET_KEY Enforcement Tests ---

def test_production_config_rejects_missing_secret_key(monkeypatch):
    """Factory must raise ValueError if SECRET_KEY is missing in production."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        create_app("production")


def test_production_config_rejects_insecure_placeholder_keys(monkeypatch):
    """Factory must reject default development placeholder keys in production."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production")
    with pytest.raises(ValueError, match="Insecure or missing SECRET_KEY"):
        create_app("production")

    monkeypatch.setenv("SECRET_KEY", "replace-with-a-strong-random-key")
    with pytest.raises(ValueError, match="Insecure or missing SECRET_KEY"):
        create_app("production")

    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValueError, match="Insecure or missing SECRET_KEY"):
        create_app("production")


def test_production_config_accepts_strong_secret_key(monkeypatch):
    """Factory accepts a strong, secure 32+ character SECRET_KEY in production."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-strong-production-secret-key-998877665544332211")
    app = create_app("production")
    assert app.config["SECRET_KEY"] == "a-very-strong-production-secret-key-998877665544332211"
    assert app.config["DEBUG"] is False


# --- 4. Supabase Storage Service Tests ---

def test_supabase_storage_disabled_by_default(monkeypatch):
    """Without credentials, Supabase Storage should report as disabled."""
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    assert is_supabase_storage_enabled() is False


def test_supabase_storage_enabled_with_credentials(monkeypatch):
    """When URL and service-role key are set, Supabase Storage is active."""
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy")
    assert is_supabase_storage_enabled() is True


def test_supabase_profile_upload_mocked_default_bucket(monkeypatch):
    """Test successful avatar upload to private Supabase Storage bucket 'profile-pictures'."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.delenv("SUPABASE_STORAGE_PROFILES_BUCKET", raising=False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.post", return_value=mock_resp) as mock_post:
        success, filename = upload_profile_picture_to_supabase(b"avatar-bytes", "avatar_123.jpg")
        assert success is True
        assert filename == "avatar_123.jpg"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "profile-pictures/avatar_123.jpg" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test-service-key"
        assert kwargs["headers"]["x-upsert"] == "true"


def test_supabase_profile_download_mocked(monkeypatch):
    """Test private profile picture download using server-side service key."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.delenv("SUPABASE_STORAGE_PROFILES_BUCKET", raising=False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"avatar-bytes-content"
    mock_resp.headers = {"Content-Type": "image/jpeg"}

    with patch("requests.get", return_value=mock_resp):
        data, c_type = download_profile_picture_from_supabase("avatar_123.jpg")
        assert data == b"avatar-bytes-content"
        assert c_type == "image/jpeg"


def test_supabase_evidence_upload_mocked_default_bucket(monkeypatch):
    """Test successful evidence upload to private Supabase Storage bucket with default 'mission-evidence'."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.delenv("SUPABASE_STORAGE_EVIDENCE_BUCKET", raising=False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.post", return_value=mock_resp) as mock_post:
        success, filename = upload_evidence_to_supabase(b"evidence-bytes", "proof_abc_123.jpg", "image/jpeg")
        assert success is True
        assert filename == "proof_abc_123.jpg"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "mission-evidence/proof_abc_123.jpg" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test-service-key"


def test_supabase_evidence_download_mocked(monkeypatch):
    """Test private evidence download using server-side service key."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("SUPABASE_STORAGE_EVIDENCE_BUCKET", "evidence")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"image-payload-data"
    mock_resp.headers = {"Content-Type": "image/jpeg"}

    with patch("requests.get", return_value=mock_resp):
        data, c_type = download_evidence_from_supabase("proof_abc_123.jpg")
        assert data == b"image-payload-data"
        assert c_type == "image/jpeg"


# --- 5. Security Check: Zero Exposure of Service Role Key ---

def test_service_role_key_never_in_rendered_pages():
    """Ensure sensitive credentials are never leaked in client templates or HTML."""
    secret_token = "SUPER_SECRET_SERVICE_ROLE_KEY_12345"
    app = create_app("testing")
    app.config["SUPABASE_SERVICE_ROLE_KEY"] = secret_token

    client = app.test_client()
    for route in ["/", "/learning/", "/missions/", "/leaderboard/", "/auth/login"]:
        response = client.get(route)
        text = response.get_data(as_text=True)
        assert secret_token not in text, f"Secret leaked in route {route}"


# --- 6. User Avatar URL Property Test ---

def test_user_avatar_url_remote_and_local():
    """Test avatar_url handles secure proxy URLs and default avatars."""
    u1 = User(full_name="Tester", email="t1@example.com", phone="123", city="C", college="U")
    u1.profile_picture = "default-avatar.svg"
    assert u1.avatar_url == "/static/images/default-avatar.svg"

    u2 = User(full_name="Tester", email="t2@example.com", phone="123", city="C", college="U")
    u2.profile_picture = "myavatar.jpg"
    assert u2.avatar_url == "/profile/avatar/myavatar.jpg"

    u3 = User(full_name="Tester", email="t3@example.com", phone="123", city="C", college="U")
    u3.profile_picture = "https://xyz.supabase.co/storage/v1/object/public/profile-pictures/myavatar.jpg"
    assert u3.avatar_url == "/profile/avatar/myavatar.jpg"


# --- 7. Profile Picture Authenticated Proxy Route Tests ---

def test_avatar_proxy_unauthenticated():
    """Unauthenticated access to private avatar must be denied (401)."""
    app = create_app("testing")
    client = app.test_client()
    res = client.get("/profile/avatar/test_avatar.jpg")
    assert res.status_code == 401


def test_avatar_proxy_authenticated_local_file(tmp_path):
    """Authenticated user can fetch local avatar via proxy."""
    app = create_app("testing")
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    # Create dummy local avatar
    img_file = tmp_path / "user_pic_123.jpg"
    img_file.write_bytes(b"\xFF\xD8\xFFdummy-jpeg")

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    with app.app_context():
        u = User(id=1, full_name="User", email="u@test.com", phone="123", password_hash="dummy", city="C", college="U")
        db.session.add(u)
        db.session.commit()

        res = client.get("/profile/avatar/user_pic_123.jpg")
        assert res.status_code == 200
        assert b"dummy-jpeg" in res.data


def test_avatar_proxy_authenticated_supabase(monkeypatch):
    """Authenticated user fetches avatar from private Supabase Storage via proxy."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")

    app = create_app("testing")
    app.config["UPLOAD_FOLDER"] = "/nonexistent/folder"

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    with app.app_context():
        u = User(id=1, full_name="User", email="u_sb@test.com", phone="123", password_hash="dummy", city="C", college="U")
        db.session.add(u)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"\xFF\xD8\xFFsupabase-avatar"
        mock_resp.headers = {"Content-Type": "image/jpeg"}

        with patch("requests.get", return_value=mock_resp):
            res = client.get("/profile/avatar/remote_pic.jpg")
            assert res.status_code == 200
            assert b"supabase-avatar" in res.data
            assert res.content_type == "image/jpeg"


# --- 7. Private and User-Authorized Evidence Access Tests ---

def test_evidence_access_authorization():
    """Verify evidence files can only be accessed by the submitting user or admins."""
    from services.submission_service import can_user_access_evidence_file

    app = create_app("testing")
    with app.app_context():
        u1 = User(full_name="User One", email="u1@test.com", phone="123", password_hash="dummyhash1", city="C", college="U")
        u2 = User(full_name="User Two", email="u2@test.com", phone="456", password_hash="dummyhash2", city="C", college="U")
        admin = User(full_name="Admin", email="admin@test.com", phone="789", password_hash="dummyhash3", city="C", college="U", is_admin=True)
        db.session.add_all([u1, u2, admin])
        db.session.commit()

        mission = Mission.query.first()
        if not mission:
            mission = Mission(
                title="Test Mission",
                slug="test-mission",
                description="Desc",
                short_description="Short",
                category="Cleanup",
                category_slug="cleanup",
                difficulty="Beginner",
                duration="30 mins",
                location="Park",
                why_it_matters="Matters",
                instructions=["Step 1"],
                proof_requirements="Photo",
                safety_guidelines=["Gloves"],
            )
            db.session.add(mission)
            db.session.commit()

        sub = Submission(
            user_id=u1.id,
            mission_id=mission.id,
            before_photo="before_test_123.jpg",
            after_photo="after_test_123.jpg",
            video_path="video_test_123.mp4",
            description="Testing authorization",
        )
        db.session.add(sub)
        db.session.commit()

        # Owner (u1) must have access
        assert can_user_access_evidence_file(u1.id, "before_test_123.jpg") is True
        assert can_user_access_evidence_file(u1.id, "after_test_123.jpg") is True
        assert can_user_access_evidence_file(u1.id, "video_test_123.mp4") is True

        # Non-owner (u2) must be denied access (Private)
        assert can_user_access_evidence_file(u2.id, "before_test_123.jpg") is False
        assert can_user_access_evidence_file(u2.id, "after_test_123.jpg") is False
        assert can_user_access_evidence_file(u2.id, "video_test_123.mp4") is False

        # Admin must have access
        assert can_user_access_evidence_file(admin.id, "before_test_123.jpg") is True

        # Non-existent file must return False
        assert can_user_access_evidence_file(u1.id, "non_existent.jpg") is False


# --- 8. No SQLite-Only Assumptions in Production ---

def test_no_sqlite_assumptions_in_app():
    """Verify that app.py uses dialect-agnostic inspection rather than SQLite-specific PRAGMA."""
    with open(os.path.join(os.path.dirname(__file__), "..", "app.py"), "r", encoding="utf-8") as f:
        content = f.read()

    assert "PRAGMA" not in content, "SQLite-specific PRAGMA found in app.py"
    assert "sqlite" not in content.lower() or "sqlite and postgresql" in content.lower(), (
        "Potential hardcoded SQLite assumptions found in app.py"
    )


# --- 9. Vercel Read-Only Filesystem & Production Deployment Regression Tests ---

def test_vercel_readonly_filesystem_instance_path(monkeypatch):
    """
    Regression test for Vercel deployment:
    Ensures instance_path is placed under /tmp/instance and never triggers:
    OSError: [Errno 30] Read-only file system: '/var/task/instance'
    """
    monkeypatch.setenv("VERCEL", "1")

    # Simulate read-only filesystem where /var/task is unwritable
    original_makedirs = os.makedirs

    def mock_makedirs(name, mode=0o777, exist_ok=False):
        normalized = str(name).replace("\\", "/")
        if "/var/task" in normalized:
            raise OSError(30, f"Read-only file system: '{name}'")
        return original_makedirs(name, mode=mode, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", mock_makedirs)

    app = create_app("testing")
    assert "/tmp/instance" in app.instance_path.replace("\\", "/")
    assert "/tmp/uploads/profiles" in app.config["UPLOAD_FOLDER"].replace("\\", "/")
    assert "/tmp/evidence" in app.config["EVIDENCE_FOLDER"].replace("\\", "/")


def test_vercel_production_rejects_sqlite_database(monkeypatch):
    """
    Regression test:
    Production on Vercel must not write SQLite databases to /tmp.
    It must require a PostgreSQL DATABASE_URL.
    """
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-strong-production-secret-key-32-chars-long")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        create_app("production")

    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        create_app("production")


def test_vercel_production_enforces_supabase_storage_credentials(monkeypatch):
    """
    Regression test:
    Production on Vercel must require SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    so user uploads are permanently persisted rather than stored in ephemeral /tmp.
    """
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-strong-production-secret-key-32-chars-long")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@db.supabase.co:5432/postgres")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        create_app("production")


def test_vercel_production_initializes_with_supabase(monkeypatch):
    """
    Verify successful initialization when all Supabase production credentials are provided on Vercel.
    """
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-strong-production-secret-key-32-chars-long")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@db.supabase.co:5432/postgres")
    monkeypatch.setenv("SUPABASE_URL", "https://xyzproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key-valid")

    app = create_app("production")
    assert "/tmp/instance" in app.instance_path.replace("\\", "/")
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith(("postgresql://", "postgresql+psycopg2://"))
    assert "/tmp/uploads/profiles" in app.config["UPLOAD_FOLDER"].replace("\\", "/")
    assert "/tmp/evidence" in app.config["EVIDENCE_FOLDER"].replace("\\", "/")


def test_local_development_preserves_standard_instance_path(monkeypatch):
    """
    Verify that outside Vercel, normal local development paths and SQLite are fully preserved.
    """
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")

    app = create_app("development")
    assert "/tmp/instance" not in app.instance_path
    assert "instance" in app.instance_path
    assert "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]


