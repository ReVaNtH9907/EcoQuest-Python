"""
EcoQuest — Community Leaderboards Routes.

Provides rankings across Global, City, and College dimensions,
with All Time, Monthly, and Weekly filters.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    g,
)
from services.leaderboard_service import (
    get_leaderboard_rankings,
    get_user_leaderboard_summary,
    get_available_cities,
    get_available_colleges,
)

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/")
def rankings():
    """
    Leaderboard rankings view.
    Supports Global, City, and College views with Weekly, Monthly, and All-Time filters.
    Returns HTML template or JSON API.
    """
    current_user = getattr(g, "current_user", None)
    current_user_id = current_user.id if current_user else None

    # Query parameters
    category = request.args.get("category", "global").lower()
    if category not in ["global", "city", "college"]:
        category = "global"

    timeframe = request.args.get("timeframe", "all_time").lower()
    if timeframe not in ["all_time", "monthly", "weekly"]:
        timeframe = "all_time"

    available_cities = get_available_cities()
    available_colleges = get_available_colleges()

    # Determine default city / college
    city = request.args.get("city")
    if not city:
        if current_user and current_user.city:
            city = current_user.city
        elif available_cities:
            city = available_cities[0]
        else:
            city = ""

    college = request.args.get("college")
    if not college:
        if current_user and current_user.college:
            college = current_user.college
        elif available_colleges:
            college = available_colleges[0]
        else:
            college = ""

    # Fetch rankings
    leaderboard_data = get_leaderboard_rankings(
        category=category,
        timeframe=timeframe,
        city=city,
        college=college,
        current_user_id=current_user_id,
        limit=100,
    )

    user_summary = None
    if current_user_id:
        user_summary = get_user_leaderboard_summary(current_user_id)

    # API / JSON support
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
        or request.is_json
    ):
        return jsonify({
            "status": "success",
            "message": "Leaderboard · rankings endpoint ready",
            "data": leaderboard_data,
            "user_summary": user_summary,
        }), 200

    return render_template(
        "leaderboard/index.html",
        data=leaderboard_data,
        user_summary=user_summary,
        available_cities=available_cities,
        available_colleges=available_colleges,
        active_category=category,
        active_timeframe=timeframe,
        active_city=city,
        active_college=college,
        user=current_user,
    )
