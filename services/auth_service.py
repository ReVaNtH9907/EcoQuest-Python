"""
EcoQuest — Authentication & User Management Service.

Encapsulates password validation, user registration, credential verification,
profile updates, and secure avatar upload management.
"""

import os
import re
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
from models import db, User

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_format(email: str) -> tuple[bool, str]:
    """Validate RFC-compliant email structure."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    clean_email = email.strip()
    if len(clean_email) > 120:
        return False, "Email address cannot exceed 120 characters."
    if not EMAIL_REGEX.match(clean_email):
        return False, "Please enter a valid email address (e.g., you@domain.com)."
    return True, clean_email.lower()


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength requirements:
      - Minimum 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one numeric digit
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number (0-9)."
    return True, ""


def validate_and_save_profile_picture(file_storage) -> tuple[bool, str, str | None]:
    """
    Validate profile picture format, enforce size constraints,
    and save securely to the upload directory with a collision-free name.
    """
    if not file_storage or not file_storage.filename:
        return True, "", None  # Optional field

    filename = file_storage.filename.strip()
    if not ("." in filename):
        return False, "Uploaded image must have a valid file extension.", None

    ext = filename.rsplit(".", 1)[1].lower()
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "webp"})
    if ext not in allowed:
        return (
            False,
            f"Invalid image format (.{ext}). Allowed formats: {', '.join(sorted(allowed))}.",
            None,
        )

    # Secure unique filename
    safe_name = secure_filename(filename)
    unique_filename = f"{uuid.uuid4().hex[:12]}_{safe_name}"

    # Read bytes for storage persistence
    file_bytes = file_storage.read()
    file_storage.seek(0)

    if not file_bytes:
        return False, "Uploaded image is empty.", None

    # Check file size (max 5 MB)
    max_size = current_app.config.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024) if current_app else 5 * 1024 * 1024
    if len(file_bytes) > max_size:
        return False, "Image size exceeds the 5 MB limit. Please select a smaller photo.", None

    # Persistent cloud storage via Supabase Storage if configured
    try:
        from services.supabase_storage import is_supabase_storage_enabled, upload_profile_picture_to_supabase
        if is_supabase_storage_enabled():
            upload_profile_picture_to_supabase(
                file_bytes, unique_filename, content_type=file_storage.mimetype
            )
    except Exception:
        pass

    # Local filesystem storage fallback and cache
    upload_dir = current_app.config.get("UPLOAD_FOLDER") if current_app else None
    if upload_dir:
        try:
            os.makedirs(upload_dir, exist_ok=True)
            destination = os.path.join(upload_dir, unique_filename)
            with open(destination, "wb") as f:
                f.write(file_bytes)
        except OSError:
            pass

    return True, "", unique_filename


def register_user(
    full_name: str,
    email: str,
    phone: str,
    password: str,
    confirm_password: str,
    city: str,
    college: str,
    profile_picture_file=None,
) -> tuple[User | None, str]:
    """
    Validate all inputs and create a new registered member.
    Enforces uniqueness, hashes passwords, and saves avatars.
    """
    # Required string validations
    full_name = (full_name or "").strip()
    phone = (phone or "").strip()
    city = (city or "").strip()
    college = (college or "").strip()

    if not full_name:
        return None, "Full name is required."
    if not phone:
        return None, "Phone number is required."
    if not city:
        return None, "City is required."
    if not college:
        return None, "College or institution is required."

    # Email validation
    valid_email, email_or_msg = validate_email_format(email)
    if not valid_email:
        return None, email_or_msg
    clean_email = email_or_msg

    # Duplicate check
    existing = User.query.filter_by(email=clean_email).first()
    if existing:
        return None, "An account with this email address already exists. Please log in."

    # Password match & strength
    if password != confirm_password:
        return None, "Passwords do not match."

    valid_pwd, pwd_msg = validate_password_strength(password)
    if not valid_pwd:
        return None, pwd_msg

    # Picture validation
    avatar_name = "default-avatar.svg"
    if profile_picture_file and profile_picture_file.filename:
        valid_pic, pic_msg, saved_name = validate_and_save_profile_picture(
            profile_picture_file
        )
        if not valid_pic:
            return None, pic_msg
        if saved_name:
            avatar_name = saved_name

    # Create entity
    user = User(
        full_name=full_name,
        email=clean_email,
        phone=phone,
        city=city,
        college=college,
        profile_picture=avatar_name,
        email_verified=False,
        phone_verified=False,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return user, "Registration successful."


def authenticate_user(email: str, password: str) -> tuple[User | None, str]:
    """Verify credentials and return the matched User entity."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None, "Please provide both email address and password."

    user = User.query.filter_by(email=email).first()
    if not user:
        return None, "Invalid email or password. Please try again."

    if not user.check_password(password):
        return None, "Invalid email or password. Please try again."

    return user, "Authenticated successfully."


def update_user_profile(
    user: User,
    full_name: str,
    phone: str,
    city: str,
    college: str,
    profile_picture_file=None,
) -> tuple[bool, str]:
    """Update editable member attributes."""
    full_name = (full_name or "").strip()
    phone = (phone or "").strip()
    city = (city or "").strip()
    college = (college or "").strip()

    if not full_name:
        return False, "Full name cannot be empty."
    if not phone:
        return False, "Phone number cannot be empty."
    if not city:
        return False, "City cannot be empty."
    if not college:
        return False, "College cannot be empty."

    user.full_name = full_name
    user.phone = phone
    user.city = city
    user.college = college

    if profile_picture_file and profile_picture_file.filename:
        valid_pic, pic_msg, saved_name = validate_and_save_profile_picture(
            profile_picture_file
        )
        if not valid_pic:
            return False, pic_msg
        if saved_name:
            user.profile_picture = saved_name

    db.session.commit()
    return True, "Profile updated successfully."


def change_user_password(
    user: User, current_password: str, new_password: str, confirm_new_password: str
) -> tuple[bool, str]:
    """Change the authenticated member's password securely."""
    if not user.check_password(current_password):
        return False, "Current password is incorrect."

    if new_password != confirm_new_password:
        return False, "New passwords do not match."

    valid_pwd, pwd_msg = validate_password_strength(new_password)
    if not valid_pwd:
        return False, pwd_msg

    if user.check_password(new_password):
        return False, "New password cannot be identical to the current password."

    user.set_password(new_password)
    db.session.commit()
    return True, "Password changed successfully."
