"""
EcoQuest — Mission Management Routes.

Endpoints for:
- Browsing environmental mission catalog with category, difficulty, search, and sorting.
- Viewing individual mission details with step-by-step instructions, why it matters, proof requirements, and safety guidelines.
- Accepting missions with duplicate prevention and repeat-participation guards.
- Tracking active, ongoing, and completed user missions.
"""

import os
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    g,
    jsonify,
    abort,
    send_from_directory,
    current_app,
)
from services.mission_service import (
    get_missions,
    get_mission_by_slug_or_id,
    accept_mission,
    withdraw_mission,
    get_user_missions,
)
from services.submission_service import (
    create_submission,
    get_user_submissions,
    get_submission_by_id,
    can_user_access_evidence_file,
    verify_submission_pipeline,
    get_user_mission_history,
    get_detailed_mission_submission,
)
from services.evidence_storage import get_evidence_path
from services.decorators import login_required
from models import UserMission

missions_bp = Blueprint("missions", __name__)

MISSION_CATEGORIES = [
    {"name": "Cleanup", "slug": "cleanup", "icon": "🧹"},
    {"name": "Tree Plantation", "slug": "tree-plantation", "icon": "🌱"},
    {"name": "Recycling", "slug": "recycling", "icon": "♻️"},
    {"name": "Water Conservation", "slug": "water-conservation", "icon": "💧"},
    {"name": "Sustainable Transport", "slug": "sustainable-transport", "icon": "🚲"},
    {"name": "Environmental Awareness", "slug": "environmental-awareness", "icon": "📢"},
]


@missions_bp.route("/")
def list_missions():
    """
    Mission discovery and catalog view.
    Supports filtering by category, difficulty, keyword search, and sorting.
    """
    category_slug = request.args.get("category", "").strip() or None
    difficulty = request.args.get("difficulty", "").strip() or None
    search_query = request.args.get("q", "").strip() or None
    sort_by = request.args.get("sort", "newest").strip() or "newest"

    current_user = getattr(g, "current_user", None)
    missions = get_missions(
        category_slug=category_slug,
        difficulty=difficulty,
        search_query=search_query,
        sort_by=sort_by,
        user=current_user,
    )

    user_missions = []
    if current_user:
        user_missions = get_user_missions(current_user.id)

    # API / JSON support
    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "status": "success",
            "total_count": len(missions),
            "missions": missions,
            "filters": {
                "category": category_slug,
                "difficulty": difficulty,
                "search": search_query,
                "sort": sort_by,
            },
        }), 200

    return render_template(
        "missions/index.html",
        missions=missions,
        categories=MISSION_CATEGORIES,
        active_category=category_slug,
        active_difficulty=difficulty,
        search_query=search_query,
        sort_by=sort_by,
        user=current_user,
        user_missions=user_missions,
    )


@missions_bp.route("/<identifier>")
def view_mission(identifier):
    """
    Individual mission detail page.
    Renders instructions, why it matters, proof requirements, safety rules, and accept button.
    """
    current_user = getattr(g, "current_user", None)
    mission = get_mission_by_slug_or_id(identifier, user=current_user)

    if not mission:
        if request.headers.get("Accept") == "application/json":
            return jsonify({"status": "error", "message": "Mission not found"}), 404
        flash("The requested mission could not be found.", "error")
        return redirect(url_for("missions.list_missions"))

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({"status": "success", "mission": mission}), 200

    return render_template(
        "missions/detail.html",
        mission=mission,
        user=current_user,
    )


@missions_bp.route("/<identifier>/accept", methods=["POST"])
def accept_action(identifier):
    """
    Accept an environmental mission.
    Prevents duplicate active missions and verifies repeat permissions.
    Does NOT award XP upon acceptance.
    """
    current_user = getattr(g, "current_user", None)
    is_json = request.is_json or request.headers.get("Accept") == "application/json"

    if not current_user:
        if is_json:
            return jsonify({
                "success": False,
                "error": "authentication_required",
                "login_url": url_for("auth.login", next=url_for("missions.view_mission", identifier=identifier)),
            }), 401
        flash("Please log in to accept missions.", "warning")
        return redirect(url_for("auth.login", next=url_for("missions.view_mission", identifier=identifier)))

    mission = get_mission_by_slug_or_id(identifier)
    if not mission:
        if is_json:
            return jsonify({"success": False, "error": "mission_not_found"}), 404
        flash("Mission not found.", "error")
        return redirect(url_for("missions.list_missions"))

    result = accept_mission(user_id=current_user.id, mission_id=mission["id"])

    if is_json:
        return jsonify(result), 200 if result["success"] else 400

    if result["success"]:
        flash(f"🎯 {result['message']}", "success")
    else:
        flash(result["message"], "warning")

    return redirect(url_for("missions.view_mission", identifier=mission["slug"]))


@missions_bp.route("/my-missions")
def my_missions():
    """
    Member's personal mission management dashboard.
    Displays accepted, ongoing, and completed missions.
    """
    current_user = getattr(g, "current_user", None)
    if not current_user:
        flash("Please log in to track your accepted missions.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    status_filter = request.args.get("status", "all").strip().lower()
    all_user_missions = get_user_missions(current_user.id)
    # Exclude withdrawn missions from active quest views
    active_user_missions = [m for m in all_user_missions if m["status"] != "withdrawn"]
    ongoing_count = len([m for m in all_user_missions if m["status"] in ["accepted", "in_progress"]])
    completed_count = len([m for m in all_user_missions if m["status"] == "completed"])

    if status_filter == "ongoing":
        filtered_missions = [m for m in all_user_missions if m["status"] in ["accepted", "in_progress"]]
    elif status_filter == "completed":
        filtered_missions = [m for m in all_user_missions if m["status"] == "completed"]
    else:
        filtered_missions = active_user_missions

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "status": "success",
            "total_accepted": len(active_user_missions),
            "missions": filtered_missions,
        }), 200

    return render_template(
        "missions/my_missions.html",
        user=current_user,
        missions=filtered_missions,
        total_accepted=len(active_user_missions),
        ongoing_count=ongoing_count,
        completed_count=completed_count,
        active_status=status_filter,
    )


@missions_bp.route("/<identifier>/withdraw", methods=["POST"])
@missions_bp.route("/my-missions/<int:user_mission_id>/withdraw", methods=["POST"])
@login_required
def withdraw_action(identifier=None, user_mission_id=None):
    """
    Withdraw from an ongoing environmental mission.
    Updates status to 'withdrawn', does not delete records, does not award XP,
    and removes mission from active quests while preserving it in Mission History.
    """
    current_user = g.current_user
    target = user_mission_id if user_mission_id is not None else identifier
    result = withdraw_mission(user_id=current_user.id, identifier=target)

    is_json = request.is_json or request.headers.get("Accept") == "application/json"
    if is_json:
        return jsonify(result), (200 if result["success"] else 400)

    if result["success"]:
        flash(f"↩️ {result['message']}", "info")
    else:
        flash(result["message"], "warning")

    return redirect(request.referrer or url_for("missions.my_missions"))


# ============================================================
# Camera-Based Mission Proof Submission Endpoints
# ============================================================

@missions_bp.route("/<identifier>/submit", methods=["GET", "POST"])
@login_required
def submit_proof(identifier):
    """
    Direct camera capture evidence submission view.
    Requires that the member has previously accepted the mission.
    Strictly accepts camera-captured media; no file/gallery inputs.
    """
    current_user = g.current_user
    mission = get_mission_by_slug_or_id(identifier, user=current_user)

    if not mission:
        if request.is_json:
            return jsonify({"success": False, "error": "mission_not_found"}), 404
        flash("Mission not found.", "error")
        return redirect(url_for("missions.list_missions"))

    # Verify user has an accepted / ongoing mission
    user_mission = UserMission.query.filter_by(
        user_id=current_user.id,
        mission_id=mission["id"],
    ).filter(UserMission.status.in_(["accepted", "in_progress"])).first()

    if not user_mission:
        if request.is_json:
            return jsonify({
                "success": False,
                "error": "mission_not_accepted",
                "message": "You must accept this mission before submitting verification proof.",
            }), 400
        flash("You must accept this mission before submitting verification proof.", "warning")
        return redirect(url_for("missions.view_mission", identifier=mission["slug"]))

    if request.method == "POST":
        is_json = request.is_json or request.headers.get("Accept") == "application/json"

        # Extract evidence payload
        before_photo = None
        after_photo = None
        video_data = None
        description = ""
        latitude = None
        longitude = None
        location_accuracy = None
        capture_timestamp = None

        if request.is_json:
            data = request.get_json() or {}
            before_photo = data.get("before_photo")
            after_photo = data.get("after_photo")
            video_data = data.get("video_data")
            description = data.get("description", "")
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            location_accuracy = data.get("location_accuracy")
            capture_timestamp = data.get("capture_timestamp")
        else:
            before_photo = request.files.get("before_photo") or request.form.get("before_photo")
            after_photo = request.files.get("after_photo") or request.form.get("after_photo")
            video_data = request.files.get("video_file") or request.form.get("video_data")
            description = request.form.get("description", "")
            latitude = request.form.get("latitude")
            longitude = request.form.get("longitude")
            location_accuracy = request.form.get("location_accuracy")
            capture_timestamp = request.form.get("capture_timestamp")

        auto_verify = False
        if request.is_json:
            auto_verify = bool(data.get("auto_verify", False))
        else:
            auto_verify = request.form.get("auto_verify") in ["true", "1", "yes"]

        result = create_submission(
            user_id=current_user.id,
            mission_id=mission["id"],
            before_photo_data=before_photo,
            after_photo_data=after_photo,
            description=description,
            video_data=video_data,
            latitude=latitude,
            longitude=longitude,
            location_accuracy=location_accuracy,
            capture_timestamp=capture_timestamp,
            auto_verify=auto_verify,
        )

        if not result["success"]:
            if is_json:
                return jsonify(result), 400
            flash(result["message"], "error")
            return redirect(url_for("missions.submit_proof", identifier=mission["slug"]))

        if is_json:
            result["redirect_url"] = url_for(
                "missions.submission_confirmation", submission_id=result["submission_id"]
            )
            return jsonify(result), 200

        flash("🎉 Mission evidence submitted successfully!", "success")
        return redirect(url_for("missions.submission_confirmation", submission_id=result["submission_id"]))

    return render_template(
        "missions/submit.html",
        mission=mission,
        user=current_user,
    )


@missions_bp.route("/submissions/<int:submission_id>/confirmation")
@login_required
def submission_confirmation(submission_id):
    """
    Displays confirmation receipt with submission reference, current status,
    and review timeline.
    """
    current_user = g.current_user
    submission = get_submission_by_id(submission_id, current_user.id)
    if not submission:
        flash("Submission record not found or access denied.", "error")
        return redirect(url_for("missions.list_submissions"))

    mission = get_mission_by_slug_or_id(submission["mission_id"])

    return render_template(
        "missions/confirmation.html",
        submission=submission,
        mission=mission,
        user=current_user,
    )


def _render_mission_history():
    """Helper to render mission history for both /history and /submissions."""
    current_user = g.current_user
    status_filter = request.args.get("status", "all").strip().lower()
    history_data = get_user_mission_history(current_user.id, status_filter=status_filter)

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "status": "success",
            "total_submissions": len(history_data["items"]),
            "counts": history_data["counts"],
            "active_filter": history_data["active_filter"],
            "missions": history_data["items"],
            "submissions": history_data["items"],
        }), 200

    return render_template(
        "missions/history.html",
        user=current_user,
        items=history_data["items"],
        submissions=history_data["items"],
        counts=history_data["counts"],
        active_filter=history_data["active_filter"],
    )


@missions_bp.route("/history")
@login_required
def mission_history():
    """
    Dedicated Mission History view displaying all previously participated missions:
    Completed, Under-review, Rejected, and In-progress with quick filters.
    """
    return _render_mission_history()


@missions_bp.route("/submissions")
@login_required
def list_submissions():
    """
    Member submission history ledger showing proof previews, status,
    and GPS verification records.
    """
    return _render_mission_history()


@missions_bp.route("/history/<int:submission_id>")
@missions_bp.route("/submissions/<int:submission_id>")
@login_required
def view_submission_detail(submission_id):
    """
    Detailed mission submission view presenting all 13 required verification items:
    1. Mission title and description
    2. Instructions and requirements
    3. Date accepted
    4. Submission date and time
    5. Before-and-after photographs
    6. Optional video evidence
    7. GPS location coordinates and accuracy
    8. Current verification status
    9. AI confidence score
    10. Verification explanation
    11. Administrator feedback
    12. XP awarded
    13. Submission history and status changes timeline
    """
    current_user = g.current_user
    try:
        detail = get_detailed_mission_submission(
            submission_id=submission_id,
            user_id=current_user.id,
            is_admin=getattr(current_user, "is_admin", False),
        )
    except PermissionError:
        abort(403)

    if not detail:
        if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
            return jsonify({"status": "error", "message": "Submission not found"}), 404
        flash("Submission record not found.", "error")
        return redirect(url_for("missions.mission_history"))

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({"status": "success", "submission": detail}), 200

    return render_template(
        "missions/submission_detail.html",
        submission=detail,
        user=current_user,
    )


@missions_bp.route("/submissions/<int:submission_id>/verify", methods=["POST"])
@login_required
def trigger_verification(submission_id):
    """
    Execute the AI verification pipeline on a submission.
    Requires submission ownership or admin rights.
    """
    current_user = g.current_user
    submission = get_submission_by_id(submission_id)
    if not submission:
        if request.is_json:
            return jsonify({"success": False, "error": "not_found"}), 404
        flash("Submission record not found.", "error")
        return redirect(url_for("missions.list_submissions"))

    if submission["user_id"] != current_user.id and not getattr(current_user, "is_admin", False):
        abort(403)

    result = verify_submission_pipeline(submission_id, auto_award_xp=True)

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify(result), 200

    if result.get("status") == "Verified":
        flash(f"🎉 Mission verified! {result.get('explanation')}", "success")
    elif result.get("status") == "Requires Manual Review":
        flash(f"⏳ Submission queued for administrator review: {result.get('explanation')}", "warning")
    elif result.get("status") == "Rejected":
        flash(f"⚠️ Submission not verified: {result.get('explanation')}", "error")

    return redirect(url_for("missions.submission_confirmation", submission_id=submission_id))


@missions_bp.route("/evidence/<filename>")
@login_required
def get_evidence(filename):
    """
    Secure authenticated route for streaming private mission evidence media.
    Enforces user ownership check: only the submission owner can view the media.
    """
    current_user = g.current_user

    # Verify user ownership of the evidence file
    if not can_user_access_evidence_file(current_user.id, filename):
        abort(403)

    abs_path = get_evidence_path(filename)
    if not abs_path:
        abort(404)

    directory = os.path.dirname(abs_path)
    clean_filename = os.path.basename(abs_path)
    return send_from_directory(directory, clean_filename)

