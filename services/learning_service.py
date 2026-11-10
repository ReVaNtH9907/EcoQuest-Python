"""
EcoQuest — Learning Academy Service.

Orchestrates:
- Curriculum database seeding and synchronization.
- Category and lesson listing with user progression state.
- Individual lesson retrieval with structured educational modules.
- Quiz evaluation, score calculation, pass/fail grading (70% passing threshold).
- Integration with centralized XP service for reward distribution.
- Aggregated user learning progress metrics.
"""

from typing import Optional, Dict, Any, List
from models import (
    db,
    User,
    LessonCategory,
    Lesson,
    QuizQuestion,
    QuizOption,
    LessonProgress,
    QuizAttempt,
    utc_now,
)
from services.curriculum_data import CURRICULUM_DATA
from services.xp_service import award_lesson_xp, calculate_user_level


def seed_learning_curriculum(db_session=None) -> int:
    """
    Idempotently seed the 8 learning categories and 16 lessons into the database.
    If already populated, skips existing records to avoid duplication.
    Returns the total count of lessons in the database.
    """
    session = db_session or db.session

    for cat_data in CURRICULUM_DATA:
        category = LessonCategory.query.filter_by(slug=cat_data["slug"]).first()
        if not category:
            category = LessonCategory(
                name=cat_data["name"],
                slug=cat_data["slug"],
                icon=cat_data["icon"],
                order=cat_data["order"],
                description=cat_data["description"],
            )
            session.add(category)
            session.flush()

        for lesson_data in cat_data["lessons"]:
            lesson = Lesson.query.filter_by(slug=lesson_data["slug"]).first()
            if not lesson:
                lesson = Lesson(
                    category_id=category.id,
                    title=lesson_data["title"],
                    slug=lesson_data["slug"],
                    summary=lesson_data["summary"],
                    introduction=lesson_data["introduction"],
                    estimated_minutes=lesson_data.get("estimated_minutes", 5),
                    xp_reward=lesson_data.get("xp_reward", 50),
                    order=lesson_data.get("order", 1),
                    icon=lesson_data.get("icon", "🌱"),
                    content_sections=lesson_data["content_sections"],
                    important_facts=lesson_data["important_facts"],
                    key_takeaways=lesson_data["key_takeaways"],
                )
                session.add(lesson)
                session.flush()

                # Add quiz questions
                for q_idx, q_data in enumerate(lesson_data.get("quiz", [])):
                    question = QuizQuestion(
                        lesson_id=lesson.id,
                        question_text=q_data["question"],
                        explanation=q_data["explanation"],
                        order=q_idx + 1,
                    )
                    session.add(question)
                    session.flush()

                    for opt_idx, opt_data in enumerate(q_data["options"]):
                        option = QuizOption(
                            question_id=question.id,
                            option_text=opt_data["text"],
                            is_correct=opt_data["is_correct"],
                            order=opt_idx + 1,
                        )
                        session.add(option)

    session.commit()
    return Lesson.query.count()


def get_categories_with_progress(user=None) -> List[Dict[str, Any]]:
    """
    Retrieve all 8 learning categories. If a user is provided,
    calculates their completed lesson count and completion percentage per category.
    """
    categories = LessonCategory.query.order_by(LessonCategory.order.asc()).all()
    user_id = user.id if user and hasattr(user, "id") else None

    # Load all user progress records if user is logged in
    user_progress_map = {}
    if user_id:
        records = LessonProgress.query.filter_by(user_id=user_id).all()
        for rec in records:
            user_progress_map[rec.lesson_id] = rec

    result = []
    for cat in categories:
        lessons = cat.lessons
        total_lessons = len(lessons)
        completed_lessons = 0

        for lsn in lessons:
            prog = user_progress_map.get(lsn.id)
            if prog and prog.completed:
                completed_lessons += 1

        pct = int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0

        result.append({
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "order": cat.order,
            "description": cat.description,
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "progress_pct": pct,
        })

    return result


def get_lessons(category_slug: Optional[str] = None, user=None) -> List[Dict[str, Any]]:
    """
    Retrieve lessons, optionally filtered by category.
    Includes user progress metadata (status, completed, highest_score, xp_awarded).
    """
    query = Lesson.query.join(LessonCategory)

    active_category = None
    if category_slug:
        active_category = LessonCategory.query.filter_by(slug=category_slug).first()
        if active_category:
            query = query.filter(Lesson.category_id == active_category.id)

    lessons = query.order_by(LessonCategory.order.asc(), Lesson.order.asc()).all()
    user_id = user.id if user and hasattr(user, "id") else None

    user_progress_map = {}
    if user_id:
        records = LessonProgress.query.filter_by(user_id=user_id).all()
        for rec in records:
            user_progress_map[rec.lesson_id] = rec

    items = []
    for lsn in lessons:
        prog = user_progress_map.get(lsn.id)
        status = prog.status if prog else "not_started"
        completed = prog.completed if prog else False
        highest_score = prog.highest_score if prog else 0.0
        xp_awarded = prog.xp_awarded if prog else False

        items.append({
            "id": lsn.id,
            "title": lsn.title,
            "slug": lsn.slug,
            "summary": lsn.summary,
            "estimated_minutes": lsn.estimated_minutes,
            "xp_reward": lsn.xp_reward,
            "icon": lsn.icon,
            "order": lsn.order,
            "category_name": lsn.category.name,
            "category_slug": lsn.category.slug,
            "category_icon": lsn.category.icon,
            "questions_count": len(lsn.questions),
            "status": status,
            "completed": completed,
            "highest_score": highest_score,
            "xp_awarded": xp_awarded,
        })

    return items


def get_lesson_by_slug(slug: str, user=None) -> Optional[Dict[str, Any]]:
    """
    Retrieve full lesson content, sections, facts, takeaways,
    and quiz questions with options. Attaches user's progress.
    """
    lesson = Lesson.query.filter_by(slug=slug).first()
    if not lesson:
        return None

    user_id = user.id if user and hasattr(user, "id") else None
    progress = None
    recent_attempt = None
    if user_id:
        progress = LessonProgress.query.filter_by(user_id=user_id, lesson_id=lesson.id).first()
        recent_attempt = (
            QuizAttempt.query.filter_by(user_id=user_id, lesson_id=lesson.id)
            .order_by(QuizAttempt.attempted_at.desc())
            .first()
        )

    # Format questions (do NOT expose is_correct in public template payload)
    questions_data = []
    for q in lesson.questions:
        options_data = []
        for opt in q.options:
            options_data.append({
                "id": opt.id,
                "text": opt.option_text,
                "order": opt.order,
            })
        questions_data.append({
            "id": q.id,
            "text": q.question_text,
            "order": q.order,
            "options": options_data,
        })

    # Find next lesson in category or overall
    next_lesson = (
        Lesson.query.filter(
            Lesson.category_id == lesson.category_id,
            Lesson.order > lesson.order,
        )
        .order_by(Lesson.order.asc())
        .first()
    )
    if not next_lesson:
        next_cat = (
            LessonCategory.query.filter(LessonCategory.order > lesson.category.order)
            .order_by(LessonCategory.order.asc())
            .first()
        )
        if next_cat and next_cat.lessons:
            next_lesson = next_cat.lessons[0]

    return {
        "id": lesson.id,
        "title": lesson.title,
        "slug": lesson.slug,
        "summary": lesson.summary,
        "introduction": lesson.introduction,
        "estimated_minutes": lesson.estimated_minutes,
        "xp_reward": lesson.xp_reward,
        "icon": lesson.icon,
        "category": {
            "id": lesson.category.id,
            "name": lesson.category.name,
            "slug": lesson.category.slug,
            "icon": lesson.category.icon,
        },
        "content_sections": lesson.content_sections or [],
        "important_facts": lesson.important_facts or [],
        "key_takeaways": lesson.key_takeaways or [],
        "questions": questions_data,
        "progress": {
            "status": progress.status if progress else "not_started",
            "completed": progress.completed if progress else False,
            "highest_score": progress.highest_score if progress else 0.0,
            "xp_awarded": progress.xp_awarded if progress else False,
            "completed_at": progress.completed_at.strftime("%d %b %Y") if progress and progress.completed_at else None,
        } if progress else None,
        "recent_attempt": {
            "score": recent_attempt.score,
            "passed": recent_attempt.passed,
            "correct_answers": recent_attempt.correct_answers,
            "total_questions": recent_attempt.total_questions,
        } if recent_attempt else None,
        "next_lesson": {
            "title": next_lesson.title,
            "slug": next_lesson.slug,
            "category_name": next_lesson.category.name,
        } if next_lesson else None,
    }


def evaluate_quiz_submission(
    user_id: int, lesson_id: int, user_answers: Dict[Any, Any]
) -> Dict[str, Any]:
    """
    Evaluate user-submitted answers for a lesson quiz.
    - user_answers: dict mapping question_id -> option_id (strings or ints)
    - Passing score is >= 70.0%
    - Saves QuizAttempt record.
    - If passed, awards 50 XP via centralized xp_service (once only).
    - Returns detailed results including explanations and user level updates.
    """
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return {"success": False, "error": "Lesson not found"}

    questions = lesson.questions
    total_questions = len(questions)
    if total_questions == 0:
        return {"success": False, "error": "This lesson has no quiz questions"}

    correct_count = 0
    feedback_list = []

    # Map answers cleanly
    sanitized_answers = {}
    for q_key, opt_val in user_answers.items():
        try:
            sanitized_answers[int(q_key)] = int(opt_val)
        except (ValueError, TypeError):
            continue

    for q in questions:
        chosen_opt_id = sanitized_answers.get(q.id)
        correct_opt = next((o for o in q.options if o.is_correct), None)
        chosen_opt = next((o for o in q.options if o.id == chosen_opt_id), None)

        is_correct = chosen_opt is not None and chosen_opt.is_correct
        if is_correct:
            correct_count += 1

        feedback_list.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "explanation": q.explanation,
            "chosen_option_id": chosen_opt_id,
            "chosen_option_text": chosen_opt.option_text if chosen_opt else "No answer selected",
            "correct_option_id": correct_opt.id if correct_opt else None,
            "correct_option_text": correct_opt.option_text if correct_opt else "",
            "is_correct": is_correct,
        })

    score = round((correct_count / total_questions) * 100.0, 1)
    passed = score >= 70.0

    # Save attempt log
    attempt = QuizAttempt(
        user_id=user_id,
        lesson_id=lesson_id,
        score=score,
        total_questions=total_questions,
        correct_answers=correct_count,
        passed=passed,
        user_answers=sanitized_answers,
        attempted_at=utc_now(),
    )
    db.session.add(attempt)
    db.session.commit()

    # Delegate XP calculation and assignment to centralized xp_service
    xp_result = award_lesson_xp(user_id=user_id, lesson_id=lesson_id, quiz_score=score)

    return {
        "success": True,
        "score": score,
        "passed": passed,
        "passing_threshold": 70.0,
        "total_questions": total_questions,
        "correct_answers": correct_count,
        "xp_awarded": xp_result["awarded"],
        "xp_amount": xp_result["xp_amount"],
        "total_xp": xp_result["total_xp"],
        "already_earned": xp_result.get("already_earned", False),
        "is_new_completion": xp_result.get("is_new_completion", False),
        "message": xp_result["message"],
        "level_info": xp_result["level_info"],
        "feedback": feedback_list,
    }


def get_user_learning_progress(user) -> Dict[str, Any]:
    """
    Compile comprehensive, user-specific learning academy progress:
    - Lessons completed
    - Total lessons available
    - Learning completion percentage
    - Total learning XP earned
    - Category-wise breakdown
    - Recommended next lessons
    """
    total_lessons = Lesson.query.count()
    if not user or not hasattr(user, "id"):
        return {
            "lessons_completed": 0,
            "total_lessons": total_lessons,
            "progress_pct": 0,
            "learning_xp": 0,
            "category_progress": [],
            "recommended_next_lessons": [],
            "next_lesson_title": "Understanding the Greenhouse Effect & Global Warming",
            "is_started": False,
        }

    user_id = user.id
    progress_records = LessonProgress.query.filter_by(user_id=user_id).all()
    completed_ids = {p.lesson_id for p in progress_records if p.completed}
    awarded_count = sum(1 for p in progress_records if p.xp_awarded)
    learning_xp = awarded_count * 50

    lessons_completed = len(completed_ids)
    progress_pct = (
        round((lessons_completed / total_lessons) * 100, 1) if total_lessons > 0 else 0
    )

    # Category-wise breakdown
    categories = LessonCategory.query.order_by(LessonCategory.order.asc()).all()
    cat_progress = []
    for cat in categories:
        cat_total = len(cat.lessons)
        cat_completed = sum(1 for l in cat.lessons if l.id in completed_ids)
        cat_pct = int((cat_completed / cat_total) * 100) if cat_total > 0 else 0
        cat_progress.append({
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "total": cat_total,
            "completed": cat_completed,
            "progress_pct": cat_pct,
        })

    # Recommended next lessons (uncompleted, prioritized by category and lesson order)
    uncompleted_lessons = (
        Lesson.query.join(LessonCategory)
        .filter(~Lesson.id.in_(completed_ids) if completed_ids else True)
        .order_by(LessonCategory.order.asc(), Lesson.order.asc())
        .limit(3)
        .all()
    )

    recommended = [
        {
            "id": l.id,
            "title": l.title,
            "slug": l.slug,
            "category_name": l.category.name,
            "category_icon": l.category.icon,
            "estimated_minutes": l.estimated_minutes,
            "xp_reward": l.xp_reward,
        }
        for l in uncompleted_lessons
    ]

    next_lesson_title = recommended[0]["title"] if recommended else "Curriculum Complete!"

    return {
        "lessons_completed": lessons_completed,
        "total_lessons": total_lessons,
        "progress_pct": progress_pct,
        "learning_xp": learning_xp,
        "category_progress": cat_progress,
        "recommended_next_lessons": recommended,
        "next_lesson_title": next_lesson_title,
        "is_started": lessons_completed > 0 or len(progress_records) > 0,
    }
