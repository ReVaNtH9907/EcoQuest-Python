"""
EcoQuest — Learning Academy Routes.

Provides endpoints for:
- Browsing environmental curriculum categories and lesson catalog.
- Viewing rich interactive lessons with structured sections, facts, and takeaways.
- Submitting interactive quizzes with immediate score calculation and feedback.
- Earning verified XP and persisting user progress records.
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
from services.learning_service import (
    get_categories_with_progress,
    get_lessons,
    get_lesson_by_slug,
    evaluate_quiz_submission,
    get_user_learning_progress,
)
from services.xp_service import get_user_xp_summary
from models import Lesson

learning_bp = Blueprint("learning", __name__)


@learning_bp.route("/")
def modules():
    """
    Lesson Discovery and Catalog view.
    Lists 8 categories, filter tabs, lesson cards, and personal learning progress.
    """
    category_slug = request.args.get("category", "").strip() or None
    current_user = getattr(g, "current_user", None)

    categories = get_categories_with_progress(user=current_user)
    lessons = get_lessons(category_slug=category_slug, user=current_user)
    learning_progress = get_user_learning_progress(user=current_user)

    # API / JSON support
    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "status": "success",
            "categories": categories,
            "lessons": lessons,
            "learning_progress": learning_progress,
            "active_category": category_slug,
        }), 200

    return render_template(
        "learning/index.html",
        categories=categories,
        lessons=lessons,
        learning_progress=learning_progress,
        active_category=category_slug,
        user=current_user,
    )


@learning_bp.route("/<slug>")
def view_lesson(slug):
    """
    Individual lesson page.
    Renders educational sections, important facts, key takeaways, and the interactive quiz.
    """
    current_user = getattr(g, "current_user", None)
    lesson = get_lesson_by_slug(slug, user=current_user)

    if not lesson:
        if request.headers.get("Accept") == "application/json":
            return jsonify({"status": "error", "message": "Lesson not found"}), 404
        flash("The requested lesson could not be found.", "error")
        return redirect(url_for("learning.modules"))

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({"status": "success", "lesson": lesson}), 200

    return render_template(
        "learning/lesson.html",
        lesson=lesson,
        user=current_user,
    )


@learning_bp.route("/<slug>/quiz", methods=["POST"])
def submit_quiz(slug):
    """
    Submit multiple-choice quiz answers for a lesson.
    Calculates score percentage (passing threshold 70%).
    Awards 50 XP to authenticated user once on first passing score.
    Returns JSON response for interactive feedback or redirects for standard form post.
    """
    current_user = getattr(g, "current_user", None)
    is_json = request.is_json or request.headers.get("Accept") == "application/json"

    if not current_user:
        if is_json:
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "login_url": url_for("auth.login", next=url_for("learning.view_lesson", slug=slug)),
            }), 401
        flash("Please log in to submit your quiz and earn XP.", "warning")
        return redirect(url_for("auth.login", next=url_for("learning.view_lesson", slug=slug)))

    lesson_record = Lesson.query.filter_by(slug=slug).first()
    if not lesson_record:
        if is_json:
            return jsonify({"success": False, "error": "Lesson not found"}), 404
        flash("Lesson not found.", "error")
        return redirect(url_for("learning.modules"))

    # Extract user answers from JSON or Form submission
    user_answers = {}
    if request.is_json:
        data = request.get_json() or {}
        # Expect either {"answers": {"1": 2, ...}} or {"1": 2} directly
        user_answers = data.get("answers", data)
    else:
        # Standard form inputs: "question_1": "3"
        for key, val in request.form.items():
            if key.startswith("question_"):
                q_id = key.replace("question_", "")
                user_answers[q_id] = val

    result = evaluate_quiz_submission(
        user_id=current_user.id,
        lesson_id=lesson_record.id,
        user_answers=user_answers,
    )

    if is_json:
        return jsonify(result), 200

    # Non-JSON form fallback
    if result.get("passed"):
        if result.get("xp_awarded"):
            flash(f"🎉 Excellent! You passed with {result['score']}% and earned 50 XP!", "success")
        else:
            flash(f"Well done! You passed with {result['score']}%. (XP already claimed)", "success")
    else:
        flash(f"You scored {result['score']}%. A score of 70% is required to pass. Try again!", "warning")

    return redirect(url_for("learning.view_lesson", slug=slug) + "#quiz-section")


@learning_bp.route("/progress")
def progress():
    """
    JSON endpoint for user learning progress and XP breakdown.
    """
    current_user = getattr(g, "current_user", None)
    if not current_user:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    learning_progress = get_user_learning_progress(current_user)
    xp_summary = get_user_xp_summary(current_user.id)

    return jsonify({
        "status": "success",
        "learning_progress": learning_progress,
        "xp_summary": xp_summary,
    }), 200
