"""
Main routes — public-facing pages (homepage, about, etc.).
"""

from flask import Blueprint, render_template, redirect, url_for, request

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Temporary homepage to confirm the application runs."""
    return render_template("index.html")


@main_bp.route("/health")
def health_check():
    """Simple health-check endpoint for monitoring."""
    return {"status": "ok"}, 200


@main_bp.route("/login")
def login_shortcut():
    """Convenience redirect to member login page."""
    return redirect(url_for("auth.login", **request.args))


@main_bp.route("/register")
def register_shortcut():
    """Convenience redirect to member registration page."""
    return redirect(url_for("auth.register", **request.args))
