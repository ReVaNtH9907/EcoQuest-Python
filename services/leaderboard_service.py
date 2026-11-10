"""
EcoQuest — Leaderboard Service.

Provides domain logic for:
- Three leaderboard categories: Global, City, and College.
- Three timeframe filters: All Time, Monthly (30 days), and Weekly (7 days).
- Deterministic rankings based on:
  1. XP earned (in selected timeframe) DESC
  2. Verified missions completed DESC
  3. Registration date (created_at) ASC
  4. User ID ASC
- Identification of logged-in user position and rank.
- Clear labelling of demo and test accounts.
- Discovery of available active cities and colleges.
"""

from datetime import timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import func, desc, asc
from models import db, User, Submission, XPTransaction, utc_now
from services.xp_service import calculate_user_level


def get_leaderboard_rankings(
    category: str = "global",
    timeframe: str = "all_time",
    city: Optional[str] = None,
    college: Optional[str] = None,
    current_user_id: Optional[int] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Retrieve ranked list of users based on category, timeframe, and location/institution.

    Args:
        category: 'global', 'city', or 'college'
        timeframe: 'all_time', 'monthly', or 'weekly'
        city: specific city name for city category filter
        college: specific college name for college category filter
        current_user_id: logged-in user's ID for highlighting and rank extraction
        limit: max rows to return in main table

    Returns:
        dict containing:
        - rankings: list of ranked user dicts
        - podium: list of top 3 users (if available)
        - user_position: dict for current_user_id rank and stats
        - active_filters: dict of applied filters
        - total_participants: total eligible users in this category
    """
    category = (category or "global").lower()
    timeframe = (timeframe or "all_time").lower()

    now = utc_now()
    cutoff_date = None
    if timeframe == "weekly":
        cutoff_date = now - timedelta(days=7)
    elif timeframe == "monthly":
        cutoff_date = now - timedelta(days=30)

    # 1. Base query for users
    user_query = User.query

    # Apply category scope
    if category == "city" and city and city.strip():
        user_query = user_query.filter(func.lower(User.city) == func.lower(city.strip()))
    elif category == "college" and college and college.strip():
        user_query = user_query.filter(func.lower(User.college) == func.lower(college.strip()))

    users = user_query.all()
    if not users:
        return {
            "rankings": [],
            "podium": [],
            "user_position": None,
            "active_filters": {
                "category": category,
                "timeframe": timeframe,
                "city": city,
                "college": college,
            },
            "total_participants": 0,
        }

    user_ids = [u.id for u in users]

    # 2. Compute verified missions completed count per user
    verified_counts_query = (
        db.session.query(
            Submission.user_id,
            func.count(Submission.id).label("verified_count"),
        )
        .filter(
            Submission.user_id.in_(user_ids),
            Submission.verification_status == "Verified",
        )
        .group_by(Submission.user_id)
        .all()
    )
    verified_map = {row[0]: row[1] for row in verified_counts_query}

    # 3. Compute XP for selected timeframe
    xp_map = {}
    if cutoff_date:
        period_xp_query = (
            db.session.query(
                XPTransaction.user_id,
                func.sum(XPTransaction.amount).label("total_period_xp"),
            )
            .filter(
                XPTransaction.user_id.in_(user_ids),
                XPTransaction.created_at >= cutoff_date,
            )
            .group_by(XPTransaction.user_id)
            .all()
        )
        for uid, p_xp in period_xp_query:
            xp_map[uid] = int(p_xp or 0)
    else:
        for u in users:
            xp_map[u.id] = int(u.total_xp or 0)

    # 4. Build leaderboard candidate objects
    candidates = []
    for u in users:
        score_xp = xp_map.get(u.id, 0)
        verified_count = verified_map.get(u.id, 0)
        level_info = calculate_user_level(u.total_xp or 0)

        candidates.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "city": u.city,
            "college": u.college,
            "score_xp": score_xp,
            "total_xp": u.total_xp or 0,
            "verified_missions": verified_count,
            "level_number": level_info["level_number"],
            "level_title": level_info["title"],
            "level_icon": level_info.get("icon", "🌱"),
            "created_at": u.created_at,
            "is_current_user": (u.id == current_user_id),
            "is_demo": getattr(u, "is_demo", False),
        })

    # 5. Deterministic sorting:
    # Rule 1: score_xp DESC
    # Rule 2: verified_missions DESC
    # Rule 3: created_at ASC (earlier registration wins ties)
    # Rule 4: user_id ASC
    candidates.sort(
        key=lambda x: (
            -x["score_xp"],
            -x["verified_missions"],
            x["created_at"] or now,
            x["user_id"],
        )
    )

    # 6. Assign ranks
    user_position = None
    rankings = []
    for index, item in enumerate(candidates):
        rank = index + 1
        item["rank"] = rank
        if item["is_current_user"]:
            user_position = item
        if index < limit:
            rankings.append(item)

    # 7. Podium (top 3)
    podium = candidates[:3] if len(candidates) >= 1 else []

    return {
        "rankings": rankings,
        "podium": podium,
        "user_position": user_position,
        "active_filters": {
            "category": category,
            "timeframe": timeframe,
            "city": city,
            "college": college,
        },
        "total_participants": len(candidates),
    }


def get_user_leaderboard_summary(user_id: int) -> Dict[str, Any]:
    """
    Compute a user's relative ranks across Global, City, and College leaderboards.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {
            "global_rank": 0,
            "city_rank": 0,
            "college_rank": 0,
            "total_xp": 0,
        }

    global_data = get_leaderboard_rankings(category="global", timeframe="all_time", current_user_id=user_id)
    city_data = get_leaderboard_rankings(category="city", city=user.city, timeframe="all_time", current_user_id=user_id)
    college_data = get_leaderboard_rankings(category="college", college=user.college, timeframe="all_time", current_user_id=user_id)

    global_rank = global_data["user_position"]["rank"] if global_data["user_position"] else 1
    city_rank = city_data["user_position"]["rank"] if city_data["user_position"] else 1
    college_rank = college_data["user_position"]["rank"] if college_data["user_position"] else 1

    return {
        "global_rank": global_rank,
        "city_rank": city_rank,
        "college_rank": college_rank,
        "global_total": global_data["total_participants"],
        "city_total": city_data["total_participants"],
        "college_total": college_data["total_participants"],
        "city_name": user.city,
        "college_name": user.college,
        "total_xp": user.total_xp or 0,
    }


def get_available_cities() -> List[str]:
    """Return distinct active user cities for dropdown filters."""
    rows = (
        db.session.query(User.city)
        .filter(User.city != None, User.city != "")
        .distinct()
        .order_by(User.city.asc())
        .all()
    )
    return [r[0] for r in rows if r[0]]


def get_available_colleges() -> List[str]:
    """Return distinct active user colleges for dropdown filters."""
    rows = (
        db.session.query(User.college)
        .filter(User.college != None, User.college != "")
        .distinct()
        .order_by(User.college.asc())
        .all()
    )
    return [r[0] for r in rows if r[0]]
