"""
EcoQuest — Centralized Experience Points (XP) & Level Progression Service.

Provides unified logic for:
- Calculating dynamic user levels, titles, badges, and progress percentages (6 tiers).
- Idempotent awarding of XP for learning lessons and quizzes.
- Idempotent awarding of XP for verified mission evidence.
- Full audit logging into immutable XPTransaction table.
- Guarding against duplicate XP exploitation and direct user modification.
- Triggering badge checks and qualifying activity streaks.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from models import (
    db,
    User,
    Lesson,
    LessonProgress,
    Mission,
    Submission,
    UserMission,
    XPTransaction,
    utc_now,
)

# Six defined progression tiers
LEVEL_TIERS = [
    (1, 0, 250, "Eco Beginner", "🌱"),
    (2, 250, 750, "Eco Explorer", "🧭"),
    (3, 750, 1500, "Eco Warrior", "🛡️"),
    (4, 1500, 3000, "Green Champion", "⭐"),
    (5, 3000, 5000, "Planet Guardian", "🌍"),
    (6, 5000, None, "Earth Protector", "👑"),
]

# Standardized baseline rewards for categories
SUGGESTED_MISSION_REWARDS = {
    "cleanup": 150,
    "tree-plantation": 200,
    "tree plantation": 200,
    "recycling": 100,
    "water-conservation": 120,
    "water conservation": 120,
    "sustainable-transport": 120,
    "sustainable transport": 120,
    "environmental-awareness": 150,
    "environmental awareness": 150,
    "awareness": 150,
    "learning-lesson": 50,
}


def calculate_user_level(total_xp: int) -> Dict[str, Any]:
    """
    Calculate level number, title, icon, and progress percentage toward next level
    from an absolute XP score.

    Six tiers:
    1. Eco Beginner — 0 XP
    2. Eco Explorer — 250 XP
    3. Eco Warrior — 750 XP
    4. Green Champion — 1,500 XP
    5. Planet Guardian — 3,000 XP
    6. Earth Protector — 5,000 XP
    """
    if total_xp is None or total_xp < 0:
        total_xp = 0

    # Top tier cap: Level 6 (Earth Protector)
    if total_xp >= 5000:
        return {
            "level_number": 6,
            "title": "Earth Protector",
            "icon": "👑",
            "total_xp": total_xp,
            "level_min_xp": 5000,
            "next_level_xp": 5000,
            "progress_pct": 100,
            "xp_to_next_level": 0,
        }

    for lvl, min_xp, next_xp, title, icon in LEVEL_TIERS:
        if next_xp is not None and min_xp <= total_xp < next_xp:
            span = max(1, next_xp - min_xp)
            progress_within = max(0, total_xp - min_xp)
            progress_pct = min(100, max(0, int((progress_within / span) * 100)))
            return {
                "level_number": lvl,
                "title": title,
                "icon": icon,
                "total_xp": total_xp,
                "level_min_xp": min_xp,
                "next_level_xp": next_xp,
                "progress_pct": progress_pct,
                "xp_to_next_level": max(0, next_xp - total_xp),
            }

    return {
        "level_number": 1,
        "title": "Eco Beginner",
        "icon": "🌱",
        "total_xp": total_xp,
        "level_min_xp": 0,
        "next_level_xp": 250,
        "progress_pct": min(100, int((total_xp / 250) * 100)),
        "xp_to_next_level": max(0, 250 - total_xp),
    }


def award_lesson_xp(user_id: int, lesson_id: int, quiz_score: float) -> Dict[str, Any]:
    """
    Safely and idempotently award XP for passing a lesson quiz.

    Rules:
    - Passing score is >= 70.0%.
    - If passed, lesson is marked completed and highest_score is updated.
    - 50 XP is awarded ONLY ONCE. Subsequent attempts will not award XP again.
    - Records an immutable XPTransaction audit entry with unique reference_id.
    - Updates User.total_xp atomically.
    - Records daily qualifying activity streak and checks for badge unlocking.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"awarded": False, "xp_amount": 0, "total_xp": 0, "message": "User not found"}

    lesson = db.session.get(Lesson, lesson_id)
    if not lesson:
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "message": "Lesson not found",
        }

    now = utc_now()
    passed = quiz_score >= 70.0

    # Retrieve or create LessonProgress
    progress = LessonProgress.query.filter_by(user_id=user_id, lesson_id=lesson_id).first()
    if not progress:
        progress = LessonProgress(
            user_id=user_id,
            lesson_id=lesson_id,
            status="not_started",
            completed=False,
            xp_awarded=False,
            highest_score=0.0,
            created_at=now,
        )
        db.session.add(progress)

    progress.last_attempt_at = now
    if quiz_score > (progress.highest_score or 0.0):
        progress.highest_score = round(quiz_score, 1)

    xp_awarded_now = False
    is_new_completion = False
    award_amount = lesson.xp_reward or 50
    tx_ref = f"XP-LES-U{user_id}-L{lesson_id}"

    if passed:
        if not progress.completed:
            progress.completed = True
            progress.completed_at = now
            progress.status = "completed"
            is_new_completion = True

        # Check both progress flag and XPTransaction log for strict idempotency
        existing_tx = XPTransaction.query.filter_by(reference_id=tx_ref).first()

        if not progress.xp_awarded and not existing_tx:
            user.total_xp = (user.total_xp or 0) + award_amount
            progress.xp_awarded = True
            xp_awarded_now = True

            # Immutable audit transaction
            tx = XPTransaction(
                user_id=user_id,
                amount=award_amount,
                source_type="lesson_quiz",
                source_id=lesson_id,
                reference_id=tx_ref,
                description=f"Passed Quiz: {lesson.title}",
                created_at=now,
            )
            db.session.add(tx)
            message = f"Congratulations! You scored {round(quiz_score, 1)}% and earned {award_amount} XP!"
        else:
            progress.xp_awarded = True
            message = f"Great work! You scored {round(quiz_score, 1)}%. (XP already awarded for this lesson)"
    else:
        if not progress.completed:
            progress.status = "in_progress"
        message = f"You scored {round(quiz_score, 1)}%. You need at least 70% to pass. Try again to earn your XP!"

    db.session.commit()

    # Trigger streak activity and badge checks if newly passed
    if passed:
        try:
            from services.gamification_service import record_qualifying_activity, evaluate_and_award_badges
            record_qualifying_activity(user_id)
            evaluate_and_award_badges(user_id)
        except Exception:
            pass

    level_info = calculate_user_level(user.total_xp or 0)

    return {
        "awarded": xp_awarded_now,
        "xp_amount": award_amount if xp_awarded_now else 0,
        "total_xp": user.total_xp or 0,
        "highest_score": progress.highest_score,
        "completed": progress.completed,
        "already_earned": progress.xp_awarded and not xp_awarded_now,
        "is_new_completion": is_new_completion,
        "message": message,
        "level_info": level_info,
    }


def award_mission_xp(
    user_id: int,
    submission_id: int,
    mission_id: int,
    reviewer_note: str = "",
) -> Dict[str, Any]:
    """
    Safely and idempotently award XP for a successfully verified mission.

    Rules:
    - Only submissions with verification_status == 'Verified' can receive XP.
    - Submissions in 'Pending', 'Processing', 'Rejected', or 'Requires Manual Review'
      CANNOT receive XP.
    - Checks submission.xp_awarded and unique XPTransaction constraint to guarantee
      idempotency and eliminate duplicate rewards.
    - If mission is non-repeatable, ensures user hasn't already collected XP for it.
    - Updates User.total_xp, creates audit XPTransaction, marks submission.xp_awarded=True,
      and updates UserMission status to 'completed'.
    - Triggers streak update and badge evaluation.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"awarded": False, "xp_amount": 0, "total_xp": 0, "message": "User not found"}

    submission = db.session.get(Submission, submission_id)
    if not submission or submission.user_id != user_id:
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "message": "Submission record not found or access denied.",
        }

    mission = db.session.get(Mission, mission_id)
    if not mission:
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "message": "Mission not found.",
        }

    # Rule: Only verified missions can receive XP
    if submission.verification_status != "Verified":
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "already_earned": False,
            "message": f"XP can only be awarded to verified submissions (Current status: {submission.verification_status}).",
            "level_info": calculate_user_level(user.total_xp or 0),
        }

    # Rule: Prevent duplicate rewards
    if submission.xp_awarded:
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "already_earned": True,
            "message": f"XP has already been awarded for submission {submission.reference_id}.",
            "level_info": calculate_user_level(user.total_xp or 0),
        }

    tx_ref = f"XP-SUB-{submission.id:05d}"
    existing_tx = XPTransaction.query.filter_by(reference_id=tx_ref).first()
    if existing_tx:
        submission.xp_awarded = True
        db.session.commit()
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "already_earned": True,
            "message": f"Transaction {tx_ref} already logged; duplicate reward prevented.",
            "level_info": calculate_user_level(user.total_xp or 0),
        }

    # Repeatability guard for non-repeatable missions
    if not mission.allow_repeat:
        prior_rewarded = (
            Submission.query.filter_by(user_id=user_id, mission_id=mission_id, xp_awarded=True)
            .filter(Submission.id != submission_id)
            .first()
        )
        if prior_rewarded:
            return {
                "awarded": False,
                "xp_amount": 0,
                "total_xp": user.total_xp or 0,
                "already_earned": True,
                "message": f"Mission '{mission.title}' is a one-time challenge. XP already collected.",
                "level_info": calculate_user_level(user.total_xp or 0),
            }

    award_amount = mission.xp_reward or SUGGESTED_MISSION_REWARDS.get(
        mission.category_slug or mission.category.lower(), 150
    )
    now = utc_now()

    try:
        # Atomic database transaction
        user.total_xp = (user.total_xp or 0) + award_amount
        submission.xp_awarded = True
        submission.xp_awarded_amount = award_amount

        # Log immutable XP transaction
        tx = XPTransaction(
            user_id=user_id,
            amount=award_amount,
            source_type="mission_verification",
            source_id=submission.id,
            reference_id=tx_ref,
            description=f"Verified Mission: {mission.title}" + (f" ({reviewer_note})" if reviewer_note else ""),
            created_at=now,
        )
        db.session.add(tx)

        # Update UserMission to completed
        user_mission = UserMission.query.filter_by(
            user_id=user_id,
            mission_id=mission_id,
        ).first()
        if user_mission:
            user_mission.status = "completed"
            user_mission.completed_at = now

        db.session.commit()

        # Update streak and badges
        try:
            from services.gamification_service import record_qualifying_activity, evaluate_and_award_badges
            record_qualifying_activity(user_id)
            evaluate_and_award_badges(user_id)
        except Exception:
            pass

        level_info = calculate_user_level(user.total_xp)

        return {
            "awarded": True,
            "xp_amount": award_amount,
            "total_xp": user.total_xp,
            "already_earned": False,
            "message": f"🎉 +{award_amount} XP awarded for verified mission '{mission.title}'!",
            "level_info": level_info,
        }

    except Exception as e:
        db.session.rollback()
        return {
            "awarded": False,
            "xp_amount": 0,
            "total_xp": user.total_xp or 0,
            "already_earned": False,
            "message": f"Transaction failed: {str(e)}",
            "level_info": calculate_user_level(user.total_xp or 0),
        }


def get_user_xp_summary(user_id: int) -> Dict[str, Any]:
    """
    Return comprehensive XP breakdown for a user based on audit transactions.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {
            "total_xp": 0,
            "learning_xp": 0,
            "mission_xp": 0,
            "level": calculate_user_level(0),
        }

    total_xp = user.total_xp or 0

    # Calculate from transactions
    learning_txs = XPTransaction.query.filter_by(user_id=user_id, source_type="lesson_quiz").all()
    learning_xp = sum(t.amount for t in learning_txs)

    mission_txs = XPTransaction.query.filter_by(user_id=user_id, source_type="mission_verification").all()
    mission_xp = sum(t.amount for t in mission_txs)

    # Fallback to direct records if transactions weren't backfilled
    if learning_xp == 0:
        awarded_lessons = LessonProgress.query.filter_by(user_id=user_id, xp_awarded=True).count()
        learning_xp = awarded_lessons * 50

    if mission_xp == 0:
        awarded_missions = Submission.query.filter_by(user_id=user_id, xp_awarded=True).all()
        mission_xp = sum(s.xp_awarded_amount or 0 for s in awarded_missions)

    return {
        "total_xp": total_xp,
        "learning_xp": learning_xp,
        "mission_xp": mission_xp,
        "level": calculate_user_level(total_xp),
        "lessons_rewarded": len(learning_txs) or LessonProgress.query.filter_by(user_id=user_id, xp_awarded=True).count(),
        "missions_rewarded": len(mission_txs) or Submission.query.filter_by(user_id=user_id, xp_awarded=True).count(),
    }
