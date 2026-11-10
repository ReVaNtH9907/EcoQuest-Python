"""
EcoQuest — Member Profile Routes.

Provides profile overview, profile editing, and password updating.
Protected with session authentication requirements.
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
from services import (
    login_required,
    update_user_profile,
    change_user_password,
    csrf_protect,
)

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/")
def view_profile():
    """Member profile overview view."""
    # API / JSON support
    if request.headers.get("Accept") == "application/json":
        if getattr(g, "current_user", None):
            return jsonify(user=g.current_user.to_dict()), 200
        return jsonify(message="Profile · view endpoint ready"), 200

    if not getattr(g, "current_user", None):
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    from services.gamification_service import get_user_badges, get_user_streak
    from services.xp_service import calculate_user_level
    user = g.current_user
    badges_info = get_user_badges(user.id)
    level_info = calculate_user_level(user.total_xp or 0)
    streak_info = get_user_streak(user.id)

    return render_template(
        "profile/view.html",
        user=user,
        badges=badges_info,
        level_info=level_info,
        streak=streak_info,
    )


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
@csrf_protect
def edit_profile():
    """Update profile details (name, phone, city, college, avatar)."""
    user = g.current_user

    if request.method == "POST":
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        city = request.form.get("city")
        college = request.form.get("college")
        profile_picture = request.files.get("profile_picture")

        success, message = update_user_profile(
            user=user,
            full_name=full_name,
            phone=phone,
            city=city,
            college=college,
            profile_picture_file=profile_picture,
        )

        if success:
            flash(message, "success")
            return redirect(url_for("profile.view_profile"))

        flash(message, "error")

    return render_template("profile/edit.html", user=user)


@profile_bp.route("/change-password", methods=["GET", "POST"])
@login_required
@csrf_protect
def change_password():
    """Change member account password."""
    user = g.current_user

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_new_password = request.form.get("confirm_new_password")

        success, message = change_user_password(
            user=user,
            current_password=current_password,
            new_password=new_password,
            confirm_new_password=confirm_new_password,
        )

        if success:
            flash(message, "success")
            return redirect(url_for("profile.view_profile"))

        flash(message, "error")

    return render_template("profile/change_password.html", user=user)
