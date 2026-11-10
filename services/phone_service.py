"""
EcoQuest — Phone Verification Service Interface.

Structures phone number verification so an SMS provider (Twilio, AWS SNS, etc.)
can be cleanly integrated later without simulating fake SMS delivery.
"""

import logging
from models import db, User

logger = logging.getLogger("ecoquest.phone")


class PhoneVerificationProvider:
    """Abstract interface for external SMS / telephony providers."""

    def send_sms_otp(self, to_phone: str, otp_code: str) -> dict:
        raise NotImplementedError("SMS provider not configured.")


class UnconfiguredSMSProvider(PhoneVerificationProvider):
    """Default stub provider documenting pending SMS infrastructure."""

    def send_sms_otp(self, to_phone: str, otp_code: str) -> dict:
        logger.info(
            f"[SMS PROVIDER NOTICE] SMS delivery requested for {to_phone}. "
            f"Provider integration pending (SMS credentials not attached)."
        )
        return {
            "delivered": False,
            "provider": None,
            "status": "pending_integration",
            "message": "SMS delivery provider not configured. Ready for Twilio / AWS SNS integration.",
        }


# Active provider instance (can be swapped via config in the future)
_active_provider: PhoneVerificationProvider = UnconfiguredSMSProvider()


def initiate_phone_verification(user_id: int, phone_number: str) -> dict:
    """
    Interface to initiate a phone OTP challenge.
    Does not pretend an SMS was delivered.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"success": False, "message": "User not found."}

    # Delegate to the provider interface
    provider_result = _active_provider.send_sms_otp(phone_number, "000000")
    return {
        "success": True,
        "phone": phone_number,
        "phone_verified": user.phone_verified,
        "provider_status": provider_result,
    }
