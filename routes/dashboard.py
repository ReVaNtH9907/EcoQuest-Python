"""
EcoQuest — Member Dashboard Routes.

Displays authenticated user overview, progress stats, environmental impact metrics,
recommended missions, learning progress, and recent activity feed.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    g,
    jsonify,
)
from services import get_user_dashboard_data

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def overview():
    """Member dashboard overview view."""
    # API / JSON support
    if request.headers.get("Accept") == "application/json":
        if getattr(g, "current_user", None):
            data = get_user_dashboard_data(g.current_user)
            return jsonify(message="Dashboard · overview endpoint ready", data=data), 200
        return jsonify(message="Dashboard · overview endpoint ready"), 200

    if not getattr(g, "current_user", None):
        flash("Please log in to view your dashboard.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    dashboard_data = get_user_dashboard_data(g.current_user)
    return render_template(
        "dashboard/overview.html",
        user=g.current_user,
        data=dashboard_data,
    )
