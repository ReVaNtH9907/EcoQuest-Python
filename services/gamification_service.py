"""
EcoQuest — Gamification Service.

Manages:
- Achievement badges (definitions, idempotent seeding, automated unlocking, duplicate prevention).
- Daily activity streaks (qualifying activity tracking, consecutive day incrementation, lapse calculation).
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from models import (
    db,
    User,
    Badge,
    UserBadge,
    UserStreak,
    Submission,
    LessonProgress,
    utc_now,
)

# Core 6 achievement badges
DEFAULT_BADGES = [
    {
        "slug": "first-steps",
        "name": "First Steps",
        "icon": "🌱",
        "category": "Missions",
        "description": "Completed your first verified real-world environmental mission.",
        "requirement_description": "Complete 1 verified mission",
    },
    {
        "slug": "green-thumb",
        "name": "Green Thumb",
        "icon": "🌳",
        "category": "Restoration",
        "description": "Planted an indigenous tree and provided verified camera evidence.",
        "requirement_description": "Complete 1 verified tree plantation mission",
    },
    {
        "slug": "waste-warrior",
        "name": "Waste Warrior",
        "icon": "♻️",
        "category": "Cleanup",
        "description": "Demonstrated persistent cleanup and recycling action across 5 verified missions.",
        "requirement_description": "Complete 5 cleanup or recycling missions",
    },
    {
        "slug": "water-saver",
        "name": "Water Saver",
        "icon": "💧",
        "category": "Conservation",
        "description": "Conserved and protected freshwater resources across 3 verified missions.",
        "requirement_description": "Complete 3 verified water conservation missions",
    },
    {
        "slug": "knowledge-seeker",
        "name": "Knowledge Seeker",
        "icon": "📚",
        "category": "Learning",
        "description": "Mastered ecological principles by completing 5 lessons with passing quizzes.",
        "requirement_description": "Complete 5 learning academy lessons",
    },
    {
        "slug": "eco-champion",
        "name": "Eco Champion",
        "icon": "🏆",
        "category": "Milestone",
        "description": "An environmental hero with twenty verified sustainability missions.",
        "requirement_description": "Complete 20 verified missions",
    },
]


def seed_badges(db_session=None) -> int:
    """
    Idempotently seed the 6 core achievement badges into the database.
    Updates existing records or inserts new ones.
    """
    session = db_session or db.session

    for b_data in DEFAULT_BADGES:
        badge = Badge.query.filter_by(slug=b_data["slug"]).first()
        if not badge:
            badge = Badge(
                slug=b_data["slug"],
                name=b_data["name"],
                icon=b_data["icon"],
                category=b_data["category"],
                description=b_data["description"],
                requirement_description=b_data["requirement_description"],
                created_at=utc_now(),
            )
            session.add(badge)
        else:
            badge.name = b_data["name"]
            badge.icon = b_data["icon"]
            badge.category = b_data["category"]
            badge.description = b_data["description"]
            badge.requirement_description = b_data["requirement_description"]

    session.commit()
    return Badge.query.count()


def evaluate_and_award_badges(user_id: int) -> List[Dict[str, Any]]:
    """
    Evaluate user activity against all badge rules and automatically award any
    unlocked badges. Prevents duplicate awards via UserBadge unique constraint
    and pre-award checks.

    Returns:
        List of newly awarded badge dictionaries.
    """
    user = db.session.get(User, user_id)
    if not user:
        return []

    # Ensure badges are seeded
    if Badge.query.count() == 0:
        seed_badges(db.session)

    # 1. Fetch user verified submissions
    verified_submissions = (
        Submission.query.filter_by(user_id=user_id, verification_status="Verified").all()
    )
    verified_count = len(verified_submissions)

    # Category counts
    tree_count = 0
    waste_count = 0
    water_count = 0

    for s in verified_submissions:
        if not s.mission:
            continue
        cat_lower = (s.mission.category or "").lower()
        slug_lower = (s.mission.category_slug or "").lower()

        if "tree" in cat_lower or "tree" in slug_lower or "plant" in cat_lower:
            tree_count += 1
        if "cleanup" in cat_lower or "clean" in slug_lower or "recycl" in cat_lower or "recycl" in slug_lower:
            waste_count += 1
        if "water" in cat_lower or "water" in slug_lower:
            water_count += 1

    # 2. Fetch completed lessons count
    completed_lessons_count = (
        LessonProgress.query.filter_by(user_id=user_id, completed=True).count()
    )

    # Define eligibility lookup
    eligibility = {
        "first-steps": verified_count >= 1,
        "green-thumb": tree_count >= 1,
        "waste-warrior": waste_count >= 5,
        "water-saver": water_count >= 3,
        "knowledge-seeker": completed_lessons_count >= 5,
        "eco-champion": verified_count >= 20,
    }

    # Fetch currently earned badge IDs for this user
    existing_earned = {
        ub.badge_id for ub in UserBadge.query.filter_by(user_id=user_id).all()
    }

    newly_awarded = []
    all_badges = Badge.query.all()

    for badge in all_badges:
        is_eligible = eligibility.get(badge.slug, False)
        if is_eligible and badge.id not in existing_earned:
            try:
                user_badge = UserBadge(
                    user_id=user_id,
                    badge_id=badge.id,
                    awarded_at=utc_now(),
                )
                db.session.add(user_badge)
                db.session.flush()  # Flush to catch constraint errors early
                newly_awarded.append(badge.to_dict())
                existing_earned.add(badge.id)
            except Exception:
                db.session.rollback()

    if newly_awarded:
        db.session.commit()

    return newly_awarded


def get_user_badges(user_id: int) -> Dict[str, Any]:
    """
    Retrieve comprehensive badge status for a user, separating earned vs locked badges.
    """
    # Ensure badges are seeded
    if Badge.query.count() == 0:
        seed_badges(db.session)

    all_badges = Badge.query.order_by(Badge.id.asc()).all()
    user_badges_map = {
        ub.badge_id: ub
        for ub in UserBadge.query.filter_by(user_id=user_id).all()
    }

    earned = []
    locked = []

    for badge in all_badges:
        ub = user_badges_map.get(badge.id)
        if ub:
            earned.append({
                "id": badge.id,
                "slug": badge.slug,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "category": badge.category,
                "requirement_description": badge.requirement_description,
                "is_earned": True,
                "awarded_at": ub.awarded_at.strftime("%d %b %Y") if ub.awarded_at else "",
                "awarded_at_iso": ub.awarded_at.isoformat() if ub.awarded_at else None,
            })
        else:
            locked.append({
                "id": badge.id,
                "slug": badge.slug,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "category": badge.category,
                "requirement_description": badge.requirement_description,
                "is_earned": False,
                "awarded_at": None,
                "awarded_at_iso": None,
            })

    return {
        "earned_badges": earned,
        "locked_badges": locked,
        "total_earned": len(earned),
        "total_available": len(all_badges),
        "completion_pct": int((len(earned) / max(1, len(all_badges))) * 100),
    }


def record_qualifying_activity(user_id: int, activity_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Record a qualifying environmental activity (quiz completion or verified mission).
    Updates current streak and longest streak idempotently.
    Prevents duplicate increments on the same calendar day.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"current_streak": 0, "longest_streak": 0, "last_activity_date": None}

    target_date = activity_date or utc_now().date()
    streak = UserStreak.query.filter_by(user_id=user_id).first()

    if not streak:
        streak = UserStreak(
            user_id=user_id,
            current_streak=1,
            longest_streak=1,
            last_activity_date=target_date,
            updated_at=utc_now(),
        )
        db.session.add(streak)
    else:
        if streak.last_activity_date == target_date:
            # Same day activity: idempotent, streak already counted for today
            pass
        elif streak.last_activity_date == target_date - timedelta(days=1):
            # Consecutive day: increment current streak
            streak.current_streak += 1
            if streak.current_streak > streak.longest_streak:
                streak.longest_streak = streak.current_streak
            streak.last_activity_date = target_date
            streak.updated_at = utc_now()
        else:
            # Missed day: reset current streak to 1
            streak.current_streak = 1
            if streak.longest_streak < 1:
                streak.longest_streak = 1
            streak.last_activity_date = target_date
            streak.updated_at = utc_now()

    db.session.commit()

    return {
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "last_activity_date": streak.last_activity_date.isoformat() if streak.last_activity_date else None,
    }


def get_user_streak(user_id: int, current_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Retrieve user streak metrics.
    Lapses active streak to 0 if no qualifying action was performed yesterday or today.
    """
    today = current_date or utc_now().date()
    streak = UserStreak.query.filter_by(user_id=user_id).first()

    if not streak or not streak.last_activity_date:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None,
            "is_active_today": False,
        }

    days_diff = (today - streak.last_activity_date).days

    if days_diff == 0:
        active_streak = streak.current_streak
        is_active_today = True
    elif days_diff == 1:
        # Active yesterday, user can still continue streak today
        active_streak = streak.current_streak
        is_active_today = False
    else:
        # Missed 2 or more days: streak has lapsed to 0
        active_streak = 0
        is_active_today = False

    return {
        "current_streak": active_streak,
        "longest_streak": streak.longest_streak,
        "last_activity_date": streak.last_activity_date.isoformat() if streak.last_activity_date else None,
        "is_active_today": is_active_today,
    }
