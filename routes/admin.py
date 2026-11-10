"""
EcoQuest — Administrator Mission Review & Verification Console.

Provides protected endpoints for:
- Monitoring submission queues and verification states.
- Viewing raw evidence, mission criteria, and AI vision findings.
- Approving submissions and triggering safe, idempotent XP awards.
- Rejecting submissions with detailed feedback.
- Requesting supplementary evidence for suspicious submissions.
- Enforcing strict @admin_required authorization guards.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    g,
    abort,
)
from services.decorators import login_required, admin_required
from services.submission_service import (
    get_all_submissions_for_admin,
    get_submission_by_id,
    admin_review_submission,
    verify_submission_pipeline,
)
from services.mission_service import get_mission_by_slug_or_id
from models import db, Submission, User

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@admin_required
def admin_home():
    """Redirect to reviews queue."""
    return redirect(url_for("admin.list_reviews"))


@admin_bp.route("/reviews")
@admin_required
def list_reviews():
    """
    Submissions review queue.
    Supports filtering by status: 'Requires Manual Review', 'Pending Verification', 'Verified', 'Rejected'.
    """
    status_filter = request.args.get("status", "all").strip()
    all_submissions = get_all_submissions_for_admin(status_filter=None)

    # Compute quick queue counters
    total_count = len(all_submissions)
    review_needed_count = len([s for s in all_submissions if s["verification_status"] == "Requires Manual Review"])
    pending_count = len([s for s in all_submissions if s["verification_status"] in ["Pending", "Pending Verification"]])
    verified_count = len([s for s in all_submissions if s["verification_status"] == "Verified"])
    rejected_count = len([s for s in all_submissions if s["verification_status"] == "Rejected"])

    # Apply filter
    if status_filter != "all":
        if status_filter == "pending":
            filtered = [s for s in all_submissions if s["verification_status"] in ["Pending", "Pending Verification"]]
        elif status_filter == "review":
            filtered = [s for s in all_submissions if s["verification_status"] == "Requires Manual Review"]
        else:
            filtered = [s for s in all_submissions if s["verification_status"].lower() == status_filter.lower()]
    else:
        filtered = all_submissions

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "status": "success",
            "total": total_count,
            "review_needed": review_needed_count,
            "submissions": filtered,
        }), 200

    return render_template(
        "admin/reviews_list.html",
        submissions=filtered,
        total_count=total_count,
        review_needed_count=review_needed_count,
        pending_count=pending_count,
        verified_count=verified_count,
        rejected_count=rejected_count,
        active_filter=status_filter,
        user=g.current_user,
    )


@admin_bp.route("/reviews/<int:submission_id>")
@admin_required
def view_review(submission_id):
    """
    Detailed evidence review inspector.
    Displays side-by-side camera media, mission criteria, AI findings,
    fraud checks, and admin decision console.
    """
    submission = get_submission_by_id(submission_id)
    if not submission:
        flash("Submission record not found.", "error")
        return redirect(url_for("admin.list_reviews"))

    mission = get_mission_by_slug_or_id(submission["mission_id"])
    submitter = db.session.get(User, submission["user_id"])

    # Parse AI findings JSON if string
    ai_data = {}
    if submission.get("ai_findings"):
        try:
            import json
            ai_data = json.loads(submission["ai_findings"])
        except Exception:
            ai_data = {"raw": submission["ai_findings"]}

    return render_template(
        "admin/review_detail.html",
        submission=submission,
        mission=mission,
        submitter=submitter,
        ai_data=ai_data,
        user=g.current_user,
    )


@admin_bp.route("/reviews/<int:submission_id>/decide", methods=["POST"])
@admin_required
def decide_review(submission_id):
    """
    Record an administrative review decision:
    - 'approve': Marks 'Verified' and triggers XP award.
    - 'reject': Marks 'Rejected' with reason.
    - 'request_evidence': Marks 'Requires Manual Review' with feedback request.
    """
    is_json = request.is_json or request.headers.get("Accept") == "application/json"
    if request.is_json:
        payload = request.get_json() or {}
        action = payload.get("action", "")
        reason = payload.get("reason", "")
    else:
        action = request.form.get("action", "")
        reason = request.form.get("reason", "")

    result = admin_review_submission(
        submission_id=submission_id,
        admin_user=g.current_user,
        action=action,
        reason=reason,
    )

    if not result["success"]:
        if is_json:
            return jsonify(result), 400
        flash(result["message"], "error")
        return redirect(url_for("admin.view_review", submission_id=submission_id))

    if is_json:
        return jsonify(result), 200

    flash(f"✅ {result['message']}", "success")
    return redirect(url_for("admin.list_reviews"))


@admin_bp.route("/reviews/<int:submission_id>/reverify", methods=["POST"])
@admin_required
def reverify_submission(submission_id):
    """Admin trigger to rerun the automated AI verification pipeline."""
    result = verify_submission_pipeline(submission_id, auto_award_xp=True)
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify(result), 200

    flash("🔄 AI Verification pipeline executed.", "success")
    return redirect(url_for("admin.view_review", submission_id=submission_id))
