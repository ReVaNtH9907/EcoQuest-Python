"""
EcoQuest — Email Service.

Handles delivery of verification OTPs and notification emails.
Includes an explicit, clearly labelled DEVELOPMENT MODE when SMTP
credentials are not configured. Never pretends an email was sent.
"""

import logging
from flask import current_app
from flask_mail import Mail, Message

logger = logging.getLogger("ecoquest.email")
mail = Mail()


def is_mail_configured() -> bool:
    """Check whether live SMTP credentials have been provided in configuration."""
    server = current_app.config.get("MAIL_SERVER", "").strip()
    return bool(server)


def send_otp_email(to_email: str, otp_code: str, user_name: str = "Eco Pioneer") -> dict:
    """
    Send a 6-digit verification code to the user's email address.

    Returns:
        dict with keys:
            - 'sent': bool (True ONLY if actually dispatched via SMTP)
            - 'mode': 'live' | 'development' | 'error'
            - 'code': the OTP code (only provided in development mode)
            - 'message': user-facing or log status description
    """
    subject = f"EcoQuest — Your Verification Code: {otp_code}"

    if not is_mail_configured():
        # Clearly labelled DEVELOPMENT MODE — Never pretend an email was sent
        dev_msg = (
            f"[DEVELOPMENT MODE] Real email delivery skipped: SMTP credentials not configured. "
            f"Verification OTP for {to_email}: {otp_code} (Expires in 5 minutes)"
        )
        print(f"\n=======================================================")
        print(dev_msg)
        print(f"=======================================================\n")
        logger.info(dev_msg)

        return {
            "sent": False,
            "mode": "development",
            "code": otp_code,
            "message": "Development Mode: SMTP not configured. OTP generated locally.",
        }

    # Live delivery
    try:
        msg = Message(
            subject=subject,
            recipients=[to_email],
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@ecoquest.org"),
        )
        msg.body = (
            f"Hello {user_name},\n\n"
            f"Welcome to EcoQuest!\n\n"
            f"Your 6-digit email verification code is:\n\n"
            f"    {otp_code}\n\n"
            f"This code will expire in 5 minutes.\n"
            f"If you did not request this verification, please ignore this email.\n\n"
            f"Warmly,\n"
            f"The EcoQuest Team\n"
            f"Learn. Act. Verify. Change the Planet."
        )
        msg.html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #E2E8F0; border-radius: 12px; background: #FFFFFF;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #059669; margin: 0; font-size: 24px;">🌿 EcoQuest</h1>
                <p style="color: #64748B; font-size: 14px; margin-top: 4px;">Learn. Act. Verify. Change the Planet.</p>
            </div>
            <p style="color: #111827; font-size: 16px;">Hello <strong>{user_name}</strong>,</p>
            <p style="color: #475569; font-size: 14px; line-height: 1.5;">Welcome to EcoQuest! Enter this 6-digit verification code to activate your account:</p>
            <div style="text-align: center; margin: 28px 0;">
                <span style="display: inline-block; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #047857; background: #ECFDF5; padding: 12px 28px; border-radius: 8px; border: 1px dashed #059669;">
                    {otp_code}
                </span>
            </div>
            <p style="color: #64748B; font-size: 12px; text-align: center;">This code will expire in <strong>5 minutes</strong>. If you did not request this, please ignore this email.</p>
        </div>
        """
        mail.send(msg)
        logger.info(f"Verification email successfully dispatched to {to_email}.")
        return {
            "sent": True,
            "mode": "live",
            "message": f"Verification code sent to {to_email}.",
        }
    except Exception as e:
        logger.error(f"Failed to deliver email to {to_email}: {e}")
        return {
            "sent": False,
            "mode": "error",
            "message": f"Could not deliver email: {str(e)}",
        }
