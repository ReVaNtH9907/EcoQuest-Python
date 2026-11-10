"""
EcoQuest — Authentication & User Management Test Suite.

Verifies:
  1. Successful member registration
  2. Duplicate email prevention
  3. Form validation (email format, password strength)
  4. Profile picture upload and validation
  5. Email OTP generation, dev-mode delivery, and verification
  6. OTP expiration handling
  7. OTP resend rate limiting
  8. Login authentication (valid & invalid credentials)
  9. Session persistence and @login_required route protection
  10. Profile viewing and profile editing
  11. Password changing
  12. Logout and session invalidation
"""

import os
import sys
import io
from datetime import timedelta
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db, User, OTPVerification, utc_now


@pytest.fixture
def app():
    """Create and configure a testing Flask app instance."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


def test_successful_registration(client, app):
    """New members can register with full details and trigger an OTP."""
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Greta Thunberg",
            "email": "greta@ecoquest.org",
            "phone": "+1 555-0199",
            "city": "Stockholm",
            "college": "Climate Action Academy",
            "password": "EcoPassword123",
            "confirm_password": "EcoPassword123",
        },
        follow_redirects=False,
    )
    # Should redirect to OTP verification page
    assert response.status_code == 302
    assert "/auth/verify-otp" in response.headers["Location"]

    with app.app_context():
        user = User.query.filter_by(email="greta@ecoquest.org").first()
        assert user is not None
        assert user.full_name == "Greta Thunberg"
        assert user.city == "Stockholm"
        assert user.email_verified is False
        assert user.check_password("EcoPassword123") is True
        # Plaintext password is NEVER stored
        assert user.password_hash != "EcoPassword123"

        # Check OTP record created
        otp = OTPVerification.query.filter_by(user_id=user.id, purpose="email_verification").first()
        assert otp is not None
        assert len(otp.code) == 6
        assert otp.used is False


def test_duplicate_email_prevention(client, app):
    """Registering with an already registered email must be rejected."""
    client.post(
        "/auth/register",
        data={
            "full_name": "User One",
            "email": "duplicate@ecoquest.org",
            "phone": "+1 555-0001",
            "city": "Denver",
            "college": "Eco Tech Institute",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Second registration with same email
    res2 = client.post(
        "/auth/register",
        data={
            "full_name": "User Two",
            "email": "duplicate@ecoquest.org",
            "phone": "+1 555-0002",
            "city": "Boulder",
            "college": "Colorado State",
            "password": "Password456",
            "confirm_password": "Password456",
        },
    )
    assert res2.status_code == 400
    assert b"already exists" in res2.data


def test_password_strength_validation(client):
    """Weak passwords must be rejected."""
    # Too short (< 8 chars)
    r1 = client.post(
        "/auth/register",
        data={
            "full_name": "Test",
            "email": "test@ecoquest.org",
            "phone": "555",
            "city": "A",
            "college": "B",
            "password": "Short1",
            "confirm_password": "Short1",
        },
    )
    assert r1.status_code == 400
    assert b"at least 8 characters" in r1.data

    # No uppercase
    r2 = client.post(
        "/auth/register",
        data={
            "full_name": "Test",
            "email": "test2@ecoquest.org",
            "phone": "555",
            "city": "A",
            "college": "B",
            "password": "lowercaseonly123",
            "confirm_password": "lowercaseonly123",
        },
    )
    assert r2.status_code == 400
    assert b"uppercase" in r2.data


def test_email_format_validation(client):
    """Invalid email addresses must be rejected."""
    r = client.post(
        "/auth/register",
        data={
            "full_name": "Invalid Email User",
            "email": "not-an-email",
            "phone": "555",
            "city": "Austin",
            "college": "UT",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    assert r.status_code == 400
    assert b"valid email" in r.data


def test_profile_picture_upload(client, app):
    """Profile pictures can be uploaded and validated."""
    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"dummy image data")
    fake_png.name = "my_avatar.png"

    response = client.post(
        "/auth/register",
        data={
            "full_name": "Avatar User",
            "email": "avatar@ecoquest.org",
            "phone": "+1 555-0100",
            "city": "Portland",
            "college": "Reed College",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
            "profile_picture": (fake_png, "my_avatar.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(email="avatar@ecoquest.org").first()
        assert user is not None
        assert user.profile_picture.endswith(".png")
        assert user.profile_picture != "default-avatar.svg"


def test_email_otp_verification(client, app):
    """Correct 6-digit OTP activates the account and establishes a session."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Jane Goodall",
            "email": "jane@ecoquest.org",
            "phone": "+1 555-0987",
            "city": "Cambridge",
            "college": "Darwin College",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    with app.app_context():
        user = User.query.filter_by(email="jane@ecoquest.org").first()
        otp = OTPVerification.query.filter_by(user_id=user.id, purpose="email_verification", used=False).first()
        code = otp.code

    # Submit correct OTP
    verify_res = client.post("/auth/verify-otp", data={"otp_code": code}, follow_redirects=True)
    assert verify_res.status_code == 200
    assert b"Email verified successfully" in verify_res.data

    with app.app_context():
        user = User.query.filter_by(email="jane@ecoquest.org").first()
        assert user.email_verified is True


def test_otp_expiration(client, app):
    """Expired OTPs must be rejected."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Expired User",
            "email": "expired@ecoquest.org",
            "phone": "+1 555-1111",
            "city": "Seattle",
            "college": "UW",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    with app.app_context():
        user = User.query.filter_by(email="expired@ecoquest.org").first()
        otp = OTPVerification.query.filter_by(user_id=user.id, purpose="email_verification", used=False).first()
        code = otp.code
        # Manually backdate expiration to 10 minutes in the past
        otp.expires_at = utc_now() - timedelta(minutes=10)
        db.session.commit()

    resp = client.post("/auth/verify-otp", data={"otp_code": code})
    assert resp.status_code == 400
    assert b"expired" in resp.data


def test_otp_resend_rate_limiting(client, app):
    """Requesting resend within 60 seconds must be rate-limited."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Rate Limit User",
            "email": "ratelimit@ecoquest.org",
            "phone": "+1 555-2222",
            "city": "Chicago",
            "college": "UChicago",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Immediately try to resend
    resend_resp = client.post("/auth/resend-otp", follow_redirects=True)
    assert b"Please wait" in resend_resp.data


def test_login_and_invalid_credentials(client, app):
    """Login succeeds with correct credentials and fails with wrong ones."""
    # Register user
    client.post(
        "/auth/register",
        data={
            "full_name": "Login Tester",
            "email": "login@ecoquest.org",
            "phone": "+1 555-3333",
            "city": "Boston",
            "college": "MIT",
            "password": "ValidPassword123",
            "confirm_password": "ValidPassword123",
        },
    )

    # 1. Invalid password
    bad_pass = client.post(
        "/auth/login",
        data={"email": "login@ecoquest.org", "password": "WrongPassword"},
    )
    assert bad_pass.status_code == 401
    assert b"Invalid email or password" in bad_pass.data

    # 2. Non-existent email
    bad_email = client.post(
        "/auth/login",
        data={"email": "nonexistent@ecoquest.org", "password": "AnyPassword123"},
    )
    assert bad_email.status_code == 401
    assert b"Invalid email or password" in bad_email.data

    # 3. Successful login
    good_login = client.post(
        "/auth/login",
        data={"email": "login@ecoquest.org", "password": "ValidPassword123", "remember_me": "1"},
        follow_redirects=True,
    )
    assert good_login.status_code == 200
    assert b"Welcome back, Login Tester!" in good_login.data
    assert b"login@ecoquest.org" in good_login.data


def test_protected_routes_require_login(client):
    """Unauthenticated access to protected routes redirects to login."""
    # Access profile without login
    r_profile = client.get("/profile/", follow_redirects=False)
    assert r_profile.status_code == 302
    assert "/auth/login" in r_profile.headers["Location"]

    # Access dashboard without login
    r_dash = client.get("/dashboard/", follow_redirects=False)
    assert r_dash.status_code == 302
    assert "/auth/login" in r_dash.headers["Location"]


def test_profile_edit_and_password_change(client, app):
    """Authenticated user can edit their profile and update their password."""
    # Register & Login
    client.post(
        "/auth/register",
        data={
            "full_name": "Original Name",
            "email": "profile_user@ecoquest.org",
            "phone": "555-0000",
            "city": "San Francisco",
            "college": "Berkeley",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "profile_user@ecoquest.org", "password": "Password123"})

    # Edit profile
    edit_resp = client.post(
        "/profile/edit",
        data={
            "full_name": "Updated Name",
            "phone": "555-9999",
            "city": "Oakland",
            "college": "Stanford",
        },
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200
    assert b"Updated Name" in edit_resp.data
    assert b"Oakland" in edit_resp.data

    # Change password
    change_resp = client.post(
        "/profile/change-password",
        data={
            "current_password": "Password123",
            "new_password": "NewSecretPassword456",
            "confirm_new_password": "NewSecretPassword456",
        },
        follow_redirects=True,
    )
    assert change_resp.status_code == 200
    assert b"Password changed successfully" in change_resp.data

    # Verify old password no longer works
    client.get("/auth/logout")
    bad_old = client.post("/auth/login", data={"email": "profile_user@ecoquest.org", "password": "Password123"})
    assert bad_old.status_code == 401

    # Verify new password works
    good_new = client.post(
        "/auth/login",
        data={"email": "profile_user@ecoquest.org", "password": "NewSecretPassword456"},
        follow_redirects=True,
    )
    assert good_new.status_code == 200


def test_logout(client):
    """Logging out clears the session."""
    # Register and login
    client.post(
        "/auth/register",
        data={
            "full_name": "Logout Tester",
            "email": "logout_test@ecoquest.org",
            "phone": "555-4444",
            "city": "Austin",
            "college": "UT",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "logout_test@ecoquest.org", "password": "Password123"})

    # Check authenticated
    p1 = client.get("/profile/")
    assert p1.status_code == 200

    # Logout
    logout_resp = client.get("/auth/logout", follow_redirects=True)
    assert logout_resp.status_code == 200
    assert b"signed out successfully" in logout_resp.data

    # Profile should now redirect to login
    p2 = client.get("/profile/", follow_redirects=False)
    assert p2.status_code == 302
    assert "/auth/login" in p2.headers["Location"]
