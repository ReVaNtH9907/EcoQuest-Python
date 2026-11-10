"""
EcoQuest — Dashboard Service.

Compiles member progress overview, environmental impact metrics,
gamification stats (XP, level progress, badges, daily streaks, leaderboard position),
recommended missions, learning status, and recent activity feed.
Maintains honest database records and zero states until actions are verified.
"""

from datetime import datetime
from models import QuizAttempt, LessonProgress, UserMission
from services.xp_service import calculate_user_level
from services.learning_service import get_user_learning_progress
from services.mission_service import get_user_mission_dashboard_data
from services.gamification_service import get_user_badges, get_user_streak
from services.leaderboard_service import get_user_leaderboard_summary


def get_user_dashboard_data(user) -> dict:
    """
    Compile personalized dashboard data for an authenticated member.
    Never generates fictional personal achievements.
    """
    now = datetime.now()
    formatted_date = now.strftime("%A, %d %B %Y")

    # Motivational environmental tips/messages
    motivational_messages = [
        "Ready to make a difference today? Every small action plants seeds for a greener planet.",
        "Small daily habits create massive collective environmental momentum.",
        "One clean space, one planted tree, one verified action at a time.",
        "Knowledge inspires awareness. Action creates measurable change.",
    ]
    # Pick a deterministic message based on day of year
    msg_index = now.timetuple().tm_yday % len(motivational_messages)
    motivational_message = motivational_messages[msg_index]

    # Dynamic Level and XP calculations
    user_xp = getattr(user, "total_xp", 0) or 0
    level_info = calculate_user_level(user_xp)

    # Dynamic learning curriculum progress
    learning_info = get_user_learning_progress(user)

    # Dynamic mission participation metrics
    mission_info = get_user_mission_dashboard_data(user)

    # Gamification stats: Badges, Streaks, Leaderboard standings
    user_id = getattr(user, "id", None)
    if user_id:
        user_badges = get_user_badges(user_id)
        user_streak = get_user_streak(user_id)
        leaderboard_summary = get_user_leaderboard_summary(user_id)
    else:
        user_badges = {
            "earned_badges": [],
            "locked_badges": [],
            "total_earned": 0,
            "total_available": 6,
            "completion_pct": 0,
        }
        user_streak = {
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None,
            "is_active_today": False,
        }
        leaderboard_summary = {
            "global_rank": 1,
            "city_rank": 1,
            "college_rank": 1,
            "global_total": 1,
            "city_total": 1,
            "college_total": 1,
        }

    # Progress overview (honest metrics based on real user activity)
    progress_stats = {
        "total_xp": user_xp,
        "current_level": level_info["title"],
        "level_number": level_info["level_number"],
        "level_icon": level_info.get("icon", "🌱"),
        "level_progress_pct": level_info["progress_pct"],
        "level_min_xp": level_info["level_min_xp"],
        "next_level_xp": level_info["next_level_xp"],
        "xp_to_next_level": level_info["xp_to_next_level"],
        "missions_completed": mission_info["completed_count"],
        "lessons_completed": learning_info["lessons_completed"],
        "current_streak": user_streak["current_streak"],
        "longest_streak": user_streak["longest_streak"],
        "is_active_today": user_streak["is_active_today"],
        "global_rank": leaderboard_summary["global_rank"],
        "city_rank": leaderboard_summary["city_rank"],
        "college_rank": leaderboard_summary["college_rank"],
    }

    # Honest environmental impact metrics (0 values until actual verified activity exists)
    environmental_impact = {
        "waste_collected_kg": 0.0,
        "trees_planted": 0,
        "areas_cleaned": 0,
        "volunteer_hours": 0.0,
    }

    # Dynamic recommended missions from database
    recommended_missions = mission_info["recommended_missions"]

    # Learning progress status (connected to Learning Academy database)
    learning_progress = {
        "lessons_completed": learning_info["lessons_completed"],
        "total_lessons": learning_info["total_lessons"],
        "progress_pct": learning_info["progress_pct"],
        "learning_xp": learning_info["learning_xp"],
        "next_lesson_title": learning_info["next_lesson_title"],
        "is_started": learning_info["is_started"],
        "category_progress": learning_info.get("category_progress", []),
        "recommended_next_lessons": learning_info.get("recommended_next_lessons", []),
    }

    # Recent activity feed (dynamically compiled from verified user learning and mission events)
    recent_activities = []
    if user and hasattr(user, "id"):
        # 1. Fetch user mission activities
        user_missions = (
            UserMission.query.filter_by(user_id=user.id)
            .order_by(UserMission.accepted_at.desc())
            .limit(5)
            .all()
        )
        for um in user_missions:
            m = um.mission
            if not m:
                continue
            if um.status == "completed":
                recent_activities.append({
                    "icon": "🏅",
                    "title": f"Completed Mission: {m.title}",
                    "timestamp": um.completed_at.strftime("%d %b %Y, %I:%M %p") if um.completed_at else "",
                    "category": m.category,
                    "badge": f"+{m.xp_reward} XP",
                    "badge_variant": "success",
                    "action_text": "Verified Action",
                    "dt": um.completed_at or um.accepted_at,
                })
            else:
                recent_activities.append({
                    "icon": "🎯",
                    "title": f"Accepted Mission: {m.title}",
                    "timestamp": um.accepted_at.strftime("%d %b %Y, %I:%M %p") if um.accepted_at else "",
                    "category": m.category,
                    "badge": "Ongoing",
                    "badge_variant": "primary",
                    "action_text": "In Progress",
                    "dt": um.accepted_at,
                })

        # 2. Fetch quiz attempts
        attempts = (
            QuizAttempt.query.filter_by(user_id=user.id)
            .order_by(QuizAttempt.attempted_at.desc())
            .limit(5)
            .all()
        )
        for att in attempts:
            lsn = att.lesson
            lesson_title = lsn.title if lsn else "Eco Lesson"
            cat_name = lsn.category.name if lsn and lsn.category else "Learning"
            if att.passed:
                recent_activities.append({
                    "icon": "🎓",
                    "title": f"Mastered Lesson: {lesson_title}",
                    "timestamp": att.attempted_at.strftime("%d %b %Y, %I:%M %p"),
                    "category": cat_name,
                    "badge": "+50 XP",
                    "badge_variant": "success",
                    "action_text": f"Scored {round(att.score, 1)}%",
                    "dt": att.attempted_at,
                })
            else:
                recent_activities.append({
                    "icon": "📝",
                    "title": f"Quiz Attempt: {lesson_title}",
                    "timestamp": att.attempted_at.strftime("%d %b %Y, %I:%M %p"),
                    "category": cat_name,
                    "badge": f"{round(att.score, 1)}%",
                    "badge_variant": "neutral",
                    "action_text": "Review & Retake",
                    "dt": att.attempted_at,
                })

        # Sort combined activity feed by datetime descending
        recent_activities.sort(key=lambda x: x.get("dt") or datetime.min, reverse=True)
        recent_activities = recent_activities[:6]

    return {
        "current_date": formatted_date,
        "motivational_message": motivational_message,
        "progress_stats": progress_stats,
        "level_info": level_info,
        "badges": user_badges,
        "streak": user_streak,
        "leaderboard_summary": leaderboard_summary,
        "environmental_impact": environmental_impact,
        "recommended_missions": recommended_missions,
        "learning_progress": learning_progress,
        "recent_activities": recent_activities,
        "user_missions_summary": mission_info,
    }
