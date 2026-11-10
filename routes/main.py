"""
Main routes — public-facing pages (homepage, about, etc.).
"""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Temporary homepage to confirm the application runs."""
    return render_template("index.html")


@main_bp.route("/health")
def health_check():
    """Simple health-check endpoint for monitoring."""
    return {"status": "ok"}, 200
