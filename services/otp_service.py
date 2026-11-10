"""
EcoQuest — OTP Service.

Generates random 6-digit verification codes, handles 5-minute expirations,
enforces resend rate limits, and marks records as used upon successful validation.
"""

import secrets
from datetime import timedelta
from models import db, OTPVerification, User, utc_now


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure random 6-digit numeric OTP."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def create_email_otp(
    user_id: int, purpose: str = "email_verification", expiry_minutes: int = 5
) -> tuple[OTPVerification, str]:
    """
    Generate and persist a new OTP record for a given user.
    Invalidates any previous unused OTPs for the same purpose.
    """
    # Invalidate previous unused OTPs for this user & purpose
    OTPVerification.query.filter_by(
        user_id=user_id, purpose=purpose, used=False
    ).update({"used": True})

    code = generate_otp(6)
    expires_at = utc_now() + timedelta(minutes=expiry_minutes)

    otp_record = OTPVerification(
        user_id=user_id,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        created_at=utc_now(),
        used=False,
    )
    db.session.add(otp_record)
    db.session.commit()

    return otp_record, code


def can_resend_otp(
    user_id: int, purpose: str = "email_verification", cooldown_seconds: int = 60
) -> tuple[bool, int]:
    """
    Check if enough time has passed since the most recent OTP generation.

    Returns:
        (can_resend: bool, seconds_remaining: int)
    """
    latest = (
        OTPVerification.query.filter_by(user_id=user_id, purpose=purpose)
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not latest:
        return True, 0

    elapsed = (utc_now() - latest.created_at).total_seconds()
    if elapsed >= cooldown_seconds:
        return True, 0

    remaining = int(cooldown_seconds - elapsed)
    return False, remaining


def verify_email_otp(
    user_id: int, code: str, purpose: str = "email_verification"
) -> tuple[bool, str]:
    """
    Validate a candidate OTP.

    Returns:
        (success: bool, message: str)
    """
    code = (code or "").strip()
    if not code:
        return False, "Please enter the 6-digit verification code."

    # Find the matching unused OTP record
    otp_record = (
        OTPVerification.query.filter_by(
            user_id=user_id, purpose=purpose, code=code, used=False
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        return False, "Invalid verification code. Please check and try again."

    if otp_record.is_expired:
        otp_record.used = True
        db.session.commit()
        return False, "This verification code has expired. Please request a new one."

    # Mark as used
    otp_record.used = True

    # If purpose is email verification, activate user email status
    if purpose == "email_verification":
        user = db.session.get(User, user_id)
        if user:
            user.email_verified = True

    db.session.commit()
    return True, "Email verified successfully!"
