"""
EcoQuest — CSRF Protection Utility.

Provides session-backed CSRF tokens and validation without heavy dependencies.
"""

import secrets
from functools import wraps
from flask import session, request, abort, current_app


def generate_csrf_token() -> str:
    """Retrieve existing CSRF token from session or generate a new one."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf_token(token: str) -> bool:
    """Validate candidate token against current session token."""
    # In testing mode with CSRF disabled, bypass
    if current_app.config.get("TESTING") and not current_app.config.get("WTF_CSRF_ENABLED", False):
        return True

    expected = session.get("_csrf_token")
    if not expected or not token:
        return False
    return secrets.compare_digest(expected, token)


def csrf_protect(view_fn):
    """Decorator to enforce CSRF token validation on mutating HTTP methods."""

    @wraps(view_fn)
    def decorated(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Check testing bypass
            if current_app.config.get("TESTING") and not current_app.config.get("WTF_CSRF_ENABLED", False):
                return view_fn(*args, **kwargs)

            # Check header then form
            token = (
                request.headers.get("X-CSRFToken")
                or request.headers.get("X-CSRF-Token")
                or request.form.get("csrf_token")
            )
            if not token or not validate_csrf_token(token):
                abort(400, description="Invalid or missing CSRF token.")
        return view_fn(*args, **kwargs)

    return decorated
