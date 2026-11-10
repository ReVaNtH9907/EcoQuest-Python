"""
EcoQuest — Mission Management Service.

Provides domain business logic for:
- Idempotent database seeding of 18+ sample missions across 6 categories.
- Mission catalog discovery with category, difficulty, search, and sorting.
- Mission detail retrieval with user participation state.
- Safe mission acceptance with duplicate prevention and repeat-participation guards.
- User mission tracking (accepted, ongoing, completed).
- Dashboard mission status compilation.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy import or_
from models import db, Mission, UserMission, User, utc_now
from services.mission_data import MISSIONS_DATA


def seed_missions(db_session=None) -> int:
    """
    Idempotently seed the 18 environmental missions into the database.
    Updates existing records or adds new ones to prevent duplicates.
    Returns total mission count.
    """
    session = db_session or db.session

    for data in MISSIONS_DATA:
        mission = Mission.query.filter_by(slug=data["slug"]).first()
        if not mission:
            mission = Mission.query.filter_by(title=data["title"]).first()

        if not mission:
            mission = Mission(
                title=data["title"],
                slug=data["slug"],
                category=data["category"],
                category_slug=data["category_slug"],
                difficulty=data["difficulty"],
                duration=data["duration"],
                xp_reward=data["xp_reward"],
                location=data["location"],
                short_description=data["short_description"],
                description=data["description"],
                why_it_matters=data["why_it_matters"],
                instructions=data["instructions"],
                proof_requirements=data["proof_requirements"],
                safety_guidelines=data["safety_guidelines"],
                image=data.get("image", "mission-cleanup.svg"),
                icon=data.get("icon", "🌱"),
                allow_repeat=data.get("allow_repeat", False),
                is_active=True,
            )
            session.add(mission)
        else:
            mission.title = data["title"]
            mission.slug = data["slug"]
            mission.category = data["category"]
            mission.category_slug = data["category_slug"]
            mission.difficulty = data["difficulty"]
            mission.duration = data["duration"]
            mission.xp_reward = data["xp_reward"]
            mission.location = data["location"]
            mission.short_description = data["short_description"]
            mission.description = data["description"]
            mission.why_it_matters = data["why_it_matters"]
            mission.instructions = data["instructions"]
            mission.proof_requirements = data["proof_requirements"]
            mission.safety_guidelines = data["safety_guidelines"]
            mission.image = data.get("image", "mission-cleanup.svg")
            mission.icon = data.get("icon", "🌱")
            mission.allow_repeat = data.get("allow_repeat", False)

    session.commit()
    return Mission.query.count()


def get_missions(
    category_slug: Optional[str] = None,
    difficulty: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_by: Optional[str] = "newest",
    user=None,
) -> List[Dict[str, Any]]:
    """
    Retrieve active missions with flexible filtering, search, and sorting.
    Attaches user's participation status ('not_accepted', 'accepted', 'completed').
    """
    query = Mission.query.filter_by(is_active=True)

    # 1. Filter by category
    if category_slug and category_slug != "all":
        query = query.filter(Mission.category_slug == category_slug)

    # 2. Filter by difficulty
    if difficulty and difficulty.lower() != "all":
        query = query.filter(Mission.difficulty.ilike(difficulty))

    # 3. Search query (matches title, description, location, or category)
    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(
            or_(
                Mission.title.ilike(term),
                Mission.short_description.ilike(term),
                Mission.location.ilike(term),
                Mission.category.ilike(term),
            )
        )

    # 4. Sorting
    if sort_by == "xp_high":
        query = query.order_by(Mission.xp_reward.desc())
    elif sort_by == "duration_low":
        query = query.order_by(Mission.duration.asc())
    elif sort_by == "popular":
        # Sort by total completions/participants
        query = query.order_by(Mission.xp_reward.desc(), Mission.created_at.desc())
    else:
        # Default: newest
        query = query.order_by(Mission.created_at.desc(), Mission.id.asc())

    missions = query.all()

    # User participation lookup
    user_id = user.id if user and hasattr(user, "id") else None
    user_mission_map = {}
    if user_id:
        user_records = UserMission.query.filter_by(user_id=user_id).all()
        for rec in user_records:
            user_mission_map[rec.mission_id] = rec

    results = []
    for m in missions:
        user_record = user_mission_map.get(m.id)
        user_status = user_record.status if user_record else "not_accepted"

        # Determine if user can accept
        can_accept = True
        if user_record:
            if user_record.status in ["accepted", "in_progress"]:
                can_accept = False
            elif user_record.status == "completed" and not m.allow_repeat:
                can_accept = False

        results.append({
            "id": m.id,
            "title": m.title,
            "slug": m.slug,
            "category": m.category,
            "category_slug": m.category_slug,
            "difficulty": m.difficulty,
            "duration": m.duration,
            "xp_reward": m.xp_reward,
            "location": m.location,
            "short_description": m.short_description,
            "image": m.image,
            "icon": m.icon,
            "completions_count": m.completions_count,
            "user_status": user_status,
            "can_accept": can_accept,
        })

    return results


def get_mission_by_slug_or_id(identifier: Any, user=None) -> Optional[Dict[str, Any]]:
    """
    Retrieve full mission details by integer ID or string slug.
    Attaches user's participation status and history.
    """
    if str(identifier).isdigit():
        mission = Mission.query.filter_by(id=int(identifier)).first()
    else:
        mission = Mission.query.filter_by(slug=str(identifier)).first()

    if not mission:
        return None

    user_id = user.id if user and hasattr(user, "id") else None
    user_record = None
    if user_id:
        user_record = (
            UserMission.query.filter_by(user_id=user_id, mission_id=mission.id)
            .order_by(UserMission.accepted_at.desc())
            .first()
        )

    user_status = user_record.status if user_record else "not_accepted"
    can_accept = True
    if user_record:
        if user_record.status in ["accepted", "in_progress"]:
            can_accept = False
        elif user_record.status == "completed" and not mission.allow_repeat:
            can_accept = False
        elif user_record.status == "withdrawn":
            can_accept = True

    return {
        "id": mission.id,
        "title": mission.title,
        "slug": mission.slug,
        "category": mission.category,
        "category_slug": mission.category_slug,
        "difficulty": mission.difficulty,
        "duration": mission.duration,
        "xp_reward": mission.xp_reward,
        "location": mission.location,
        "short_description": mission.short_description,
        "description": mission.description,
        "why_it_matters": mission.why_it_matters,
        "instructions": mission.instructions or [],
        "proof_requirements": mission.proof_requirements,
        "safety_guidelines": mission.safety_guidelines or [],
        "image": mission.image,
        "icon": mission.icon,
        "allow_repeat": mission.allow_repeat,
        "completions_count": mission.completions_count,
        "user_status": user_status,
        "can_accept": can_accept,
        "accepted_at": user_record.accepted_at.strftime("%d %b %Y, %I:%M %p") if user_record and user_record.accepted_at else None,
        "completed_at": user_record.completed_at.strftime("%d %b %Y, %I:%M %p") if user_record and user_record.completed_at else None,
    }


def accept_mission(user_id: int, mission_id: int) -> Dict[str, Any]:
    """
    Accept an environmental mission for an authenticated member.

    Rules:
    - Mission must exist and be active.
    - User cannot accept if they already have an active/ongoing record for this mission.
    - If user has completed this mission before and allow_repeat is False, prevent duplicate acceptance.
    - Does NOT award XP merely for accepting.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"success": False, "error": "user_not_found", "message": "User not found."}

    mission = db.session.get(Mission, mission_id)
    if not mission or not mission.is_active:
        return {"success": False, "error": "mission_not_found", "message": "Mission not found or inactive."}

    # Check for existing active or ongoing participation
    active_record = UserMission.query.filter_by(
        user_id=user_id,
        mission_id=mission_id,
    ).filter(UserMission.status.in_(["accepted", "in_progress"])).first()

    if active_record:
        return {
            "success": False,
            "error": "already_active",
            "message": "You have already accepted this mission and it is currently ongoing.",
            "user_mission_id": active_record.id,
        }

    # Check repeat permission
    if not mission.allow_repeat:
        completed_record = UserMission.query.filter_by(
            user_id=user_id,
            mission_id=mission_id,
            status="completed",
        ).first()
        if completed_record:
            return {
                "success": False,
                "error": "already_completed",
                "message": "You have already completed this mission. Repeat participation is not allowed for this challenge.",
            }

    # Create new UserMission record
    user_mission = UserMission(
        user_id=user_id,
        mission_id=mission_id,
        status="accepted",
        accepted_at=utc_now(),
    )
    db.session.add(user_mission)
    db.session.commit()

    return {
        "success": True,
        "message": f"Mission '{mission.title}' accepted! It has been added to your active quests.",
        "user_mission_id": user_mission.id,
        "mission_title": mission.title,
    }


def withdraw_mission(user_id: int, identifier: Any) -> Dict[str, Any]:
    """
    Withdraw an authenticated member from an ongoing environmental mission.

    Rules:
    - User must exist.
    - Identifier can be mission ID, mission slug, or UserMission ID.
    - User can withdraw ONLY from their own ongoing missions (status in ['accepted', 'in_progress']).
    - Users cannot withdraw from completed or verified missions.
    - Does NOT delete the UserMission record, Mission, or any existing Submission evidence.
    - Sets UserMission.status to 'withdrawn'.
    - Does NOT award XP for withdrawn missions.
    - Prevents withdrawn missions from appearing in the Active/Ongoing Missions section.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"success": False, "error": "user_not_found", "message": "User not found."}

    user_mission = None
    mission = None

    # Check if identifier is UserMission ID or Mission ID
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        int_id = int(identifier)
        # Check as UserMission ID first
        um_candidate = db.session.get(UserMission, int_id)
        if um_candidate and um_candidate.user_id == user_id:
            user_mission = um_candidate
            mission = um_candidate.mission
        else:
            # Check as Mission ID
            mission = db.session.get(Mission, int_id)

    if not mission and isinstance(identifier, str):
        mission = Mission.query.filter_by(slug=identifier).first()

    if not user_mission and mission:
        # Find active ongoing UserMission for this user and mission
        user_mission = (
            UserMission.query.filter_by(user_id=user_id, mission_id=mission.id)
            .filter(UserMission.status.in_(["accepted", "in_progress"]))
            .order_by(UserMission.accepted_at.desc())
            .first()
        )
        if not user_mission:
            # Check if there is already a completed or withdrawn record
            other_record = (
                UserMission.query.filter_by(user_id=user_id, mission_id=mission.id)
                .order_by(UserMission.accepted_at.desc())
                .first()
            )
            if other_record and other_record.status == "completed":
                return {
                    "success": False,
                    "error": "already_completed",
                    "message": "Cannot withdraw from a mission that has already been completed and verified.",
                }
            if other_record and other_record.status == "withdrawn":
                return {
                    "success": False,
                    "error": "already_withdrawn",
                    "message": "You have already withdrawn from this mission.",
                }

    if not user_mission:
        return {
            "success": False,
            "error": "not_active",
            "message": "No active or ongoing participation found for this mission.",
        }

    # Strict ownership check: restrict action to logged-in user's own record
    if user_mission.user_id != user_id:
        return {
            "success": False,
            "error": "unauthorized",
            "message": "You can only withdraw from your own missions.",
        }

    # Cannot withdraw from completed missions
    if user_mission.status == "completed":
        return {
            "success": False,
            "error": "already_completed",
            "message": "Cannot withdraw from a mission that has already been completed and verified.",
        }

    # Check if there is already a verified submission
    from models import Submission
    verified_sub = Submission.query.filter_by(
        user_id=user_id,
        mission_id=user_mission.mission_id,
        verification_status="Verified",
    ).first()
    if verified_sub:
        return {
            "success": False,
            "error": "already_verified",
            "message": "Cannot withdraw from a mission that has already been completed and verified.",
        }

    # Update status to withdrawn and persist in database
    user_mission.status = "withdrawn"
    db.session.commit()

    mission_title = mission.title if mission else (user_mission.mission.title if user_mission.mission else "Mission")

    return {
        "success": True,
        "message": f"Successfully withdrawn from '{mission_title}'.",
        "mission_id": user_mission.mission_id,
        "user_mission_id": user_mission.id,
        "mission_title": mission_title,
        "status": "withdrawn",
    }


def get_user_missions(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all missions accepted, in progress, or completed by a user.
    """
    query = UserMission.query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)

    records = query.order_by(UserMission.accepted_at.desc()).all()

    result = []
    for r in records:
        m = r.mission
        result.append({
            "user_mission_id": r.id,
            "mission_id": m.id,
            "title": m.title,
            "slug": m.slug,
            "category": m.category,
            "category_slug": m.category_slug,
            "difficulty": m.difficulty,
            "duration": m.duration,
            "xp_reward": m.xp_reward,
            "location": m.location,
            "image": m.image,
            "icon": m.icon,
            "status": r.status,
            "accepted_at": r.accepted_at.strftime("%d %b %Y, %I:%M %p") if r.accepted_at else None,
            "completed_at": r.completed_at.strftime("%d %b %Y, %I:%M %p") if r.completed_at else None,
        })
    return result


def get_user_mission_dashboard_data(user) -> Dict[str, Any]:
    """
    Compile real mission metrics from database for user dashboard integration:
    - Accepted missions count
    - Ongoing missions list
    - Completed missions count
    - Recommended missions (top unaccepted missions)
    """
    featured_slugs = [
        "clean-a-public-area",
        "plant-a-native-tree",
        "collect-recyclable-waste",
        "zero-emissions-bicycle-commute-week",
    ]

    if not user or not hasattr(user, "id"):
        # For guests, return sample recommended missions with featured pilot challenges
        all_missions = Mission.query.filter_by(is_active=True).all()
        all_missions.sort(
            key=lambda m: (0 if m.slug in featured_slugs else 1, -m.xp_reward, m.id)
        )
        sample_missions = all_missions[:4]
        return {
            "accepted_count": 0,
            "ongoing_count": 0,
            "completed_count": 0,
            "ongoing_missions": [],
            "recommended_missions": [
                {
                    "id": m.id,
                    "name": m.title,
                    "slug": m.slug,
                    "category": m.category,
                    "difficulty": m.difficulty,
                    "xp_reward": m.xp_reward,
                    "badge_variant": "primary" if m.difficulty == "Intermediate" else ("success" if m.difficulty == "Beginner" else "warning"),
                    "icon": m.icon,
                    "time_estimate": m.duration,
                    "description": m.short_description,
                }
                for m in sample_missions
            ],
        }

    user_id = user.id
    user_missions = UserMission.query.filter_by(user_id=user_id).all()

    ongoing_records = [r for r in user_missions if r.status in ["accepted", "in_progress"]]
    completed_records = [r for r in user_missions if r.status == "completed"]

    active_mission_ids = {r.mission_id for r in user_missions}

    # Featured pilot missions to prioritize for recommendation
    featured_slugs = [
        "clean-a-public-area",
        "plant-a-native-tree",
        "collect-recyclable-waste",
        "zero-emissions-bicycle-commute-week",
    ]

    # Fetch unaccepted recommended missions
    recommended_query = Mission.query.filter_by(is_active=True)
    if active_mission_ids:
        recommended_query = recommended_query.filter(~Mission.id.in_(active_mission_ids))

    all_unaccepted = recommended_query.all()
    # Sort with featured slugs first, then by XP reward
    all_unaccepted.sort(
        key=lambda m: (0 if m.slug in featured_slugs else 1, -m.xp_reward, m.id)
    )
    recommended_models = all_unaccepted[:4]

    recommended_list = [
        {
            "id": m.id,
            "name": m.title,
            "slug": m.slug,
            "category": m.category,
            "difficulty": m.difficulty,
            "xp_reward": m.xp_reward,
            "badge_variant": "primary" if m.difficulty == "Intermediate" else ("success" if m.difficulty == "Beginner" else "warning"),
            "icon": m.icon,
            "time_estimate": m.duration,
            "description": m.short_description,
        }
        for m in recommended_models
    ]

    ongoing_list = [
        {
            "id": r.mission.id,
            "user_mission_id": r.id,
            "name": r.mission.title,
            "slug": r.mission.slug,
            "category": r.mission.category,
            "difficulty": r.mission.difficulty,
            "xp_reward": r.mission.xp_reward,
            "icon": r.mission.icon,
            "status": r.status,
            "accepted_at": r.accepted_at.strftime("%d %b %Y"),
        }
        for r in ongoing_records
    ]

    return {
        "accepted_count": len(user_missions),
        "ongoing_count": len(ongoing_records),
        "completed_count": len(completed_records),
        "ongoing_missions": ongoing_list,
        "recommended_missions": recommended_list,
    }
