"""
EcoQuest — Route Decorators.

Provides access control decorators such as @login_required.
"""

from functools import wraps
from flask import g, redirect, url_for, flash, request


def login_required(view_fn):
    """
    Ensure the current request is associated with an authenticated session.
    Redirects unauthenticated visitors to the login view with a return URL.
    """

    @wraps(view_fn)
    def decorated(*args, **kwargs):
        if not getattr(g, "current_user", None):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view_fn(*args, **kwargs)

    return decorated


def admin_required(view_fn):
    """
    Ensure the current request is authenticated and has administrative privileges.
    Returns HTTP 403 Forbidden for non-admin members.
    Redirects unauthenticated visitors to the login page.
    """

    @wraps(view_fn)
    def decorated(*args, **kwargs):
        from flask import abort
        current_user = getattr(g, "current_user", None)
        if not current_user:
            flash("Please log in with administrator credentials.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view_fn(*args, **kwargs)

    return decorated
