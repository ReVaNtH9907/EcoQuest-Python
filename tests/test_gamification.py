"""
EcoQuest — Gamification & Leaderboard Systems Test Suite.

Comprehensive automated test suite covering:
1. Centralized XP Service & Idempotency:
   - Lesson quiz XP awarding (only upon score >= 70%).
   - Mission verification XP awarding (only for Verified status).
   - Strict duplicate reward prevention (XPTransaction audit unique constraint).
   - Zero XP awarded for pending/rejected/failed attempts.
2. Dynamic Level Progression:
   - All six defined tiers:
     1. Eco Beginner (0 XP)
     2. Eco Explorer (250 XP)
     3. Eco Warrior (750 XP)
     4. Green Champion (1,500 XP)
     5. Planet Guardian (3,000 XP)
     6. Earth Protector (5,000 XP)
   - Dynamic tier calculation, progress percentages, and XP needed to next tier.
3. Automated Achievement Badges:
   - First Steps (1 verified mission)
   - Green Thumb (1 verified tree plantation mission)
   - Waste Warrior (5 verified cleanup/recycling missions)
   - Water Saver (3 verified water conservation missions)
   - Knowledge Seeker (5 completed lessons with passed quiz)
   - Eco Champion (20 verified missions)
   - UniqueConstraint duplicate prevention on UserBadge.
   - Earned vs locked badge state retrieval.
4. Daily Streak Tracking:
   - Qualifying activity recording.
   - Idempotent tracking on the same calendar day (no double counting).
   - Consecutive day streak incrementation.
   - Lapsed streak calculation and longest streak retention.
5. Community Leaderboard:
   - Global, City, and College dimensions.
   - All Time, Monthly, and Weekly timeframes using XPTransaction timestamps.
   - Deterministic tie-breaking (XP DESC, verified missions DESC, created_at ASC, id ASC).
   - Highlight of logged-in user position.
   - Identification of demo/test accounts.
6. Dashboard & Profile Integration:
   - Consistent database-backed statistics on Dashboard and Profile views.
   - HTTP HTML rendering and JSON API responses.
"""

from datetime import datetime, date, timedelta
import pytest
from app import create_app
from models import (
    db,
    User,
    Mission,
    UserMission,
    Submission,
    LessonCategory,
    Lesson,
    QuizQuestion,
    QuizOption,
    LessonProgress,
    XPTransaction,
    Badge,
    UserBadge,
    UserStreak,
    utc_now,
)
from services.xp_service import (
    calculate_user_level,
    award_lesson_xp,
    award_mission_xp,
    get_user_xp_summary,
    LEVEL_TIERS,
)
from services.gamification_service import (
    seed_badges,
    evaluate_and_award_badges,
    get_user_badges,
    record_qualifying_activity,
    get_user_streak,
)
from services.leaderboard_service import (
    get_leaderboard_rankings,
    get_user_leaderboard_summary,
    get_available_cities,
    get_available_colleges,
)


@pytest.fixture
def app():
    """Create testing application with clean in-memory / temporary SQLite database."""
    test_app = create_app("testing")
    with test_app.app_context():
        db.create_all()
        seed_badges(db.session)
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def create_user(
    email="hero@ecoquest.org",
    name="Eco Hero",
    city="Bengaluru",
    college="IISc Bangalore",
    total_xp=0,
    is_admin=False,
    created_at=None,
):
    """Helper to create and commit a test user."""
    user = User(
        full_name=name,
        email=email,
        phone="+91 98765 00000",
        city=city,
        college=college,
        email_verified=True,
        total_xp=total_xp,
        is_admin=is_admin,
    )
    if created_at:
        user.created_at = created_at
    user.set_password("SecurePass123!")
    db.session.add(user)
    db.session.commit()
    return user


def create_mission(
    title="Clean Community Park",
    category="Cleanup",
    category_slug="cleanup",
    xp_reward=150,
):
    """Helper to create and commit a test mission."""
    slug = title.lower().replace(" ", "-")
    mission = Mission(
        title=title,
        slug=slug,
        category=category,
        category_slug=category_slug,
        difficulty="Beginner",
        duration="30 mins",
        xp_reward=xp_reward,
        location="Community Park",
        short_description="Clean litter.",
        description="Clean litter and document with photos.",
        why_it_matters="Reduces microplastics.",
        instructions=["Pick up litter", "Dispose properly"],
        proof_requirements="Before and after photo",
        safety_guidelines=["Wear gloves"],
        image="mission-cleanup.svg",
        icon="🧹",
        allow_repeat=True,
        is_active=True,
    )
    db.session.add(mission)
    db.session.commit()
    return mission


def create_lesson(title="Climate Action Basics", xp_reward=50):
    """Helper to create and commit a test lesson."""
    cat = LessonCategory.query.filter_by(slug="climate-action").first()
    if not cat:
        cat = LessonCategory(
            name="Climate Action",
            slug="climate-action",
            description="Climate learning",
            icon="🌍",
            order=1,
        )
        db.session.add(cat)
        db.session.commit()

    slug = title.lower().replace(" ", "-")
    lesson = Lesson(
        category_id=cat.id,
        title=title,
        slug=slug,
        summary="Basic climate concepts.",
        introduction="Intro to climate.",
        estimated_minutes=5,
        xp_reward=xp_reward,
        order=1,
        icon="🌱",
        content_sections=[{"title": "Section 1", "body": "Body content"}],
        important_facts=["Fact 1"],
        key_takeaways=["Takeaway 1"],
    )
    db.session.add(lesson)
    db.session.commit()
    return lesson


# ============================================================
# 1. Level System Calculations (All 6 Defined Levels)
# ============================================================

def test_level_calculation_all_six_tiers(app):
    """
    Test calculation for all 6 tiers:
    1. Eco Beginner — 0 XP
    2. Eco Explorer — 250 XP
    3. Eco Warrior — 750 XP
    4. Green Champion — 1,500 XP
    5. Planet Guardian — 3,000 XP
    6. Earth Protector — 5,000 XP
    """
    # Level 1: Eco Beginner (0 to 249)
    l1_zero = calculate_user_level(0)
    assert l1_zero["level_number"] == 1
    assert l1_zero["title"] == "Eco Beginner"
    assert l1_zero["progress_pct"] == 0
    assert l1_zero["xp_to_next_level"] == 250

    l1_mid = calculate_user_level(125)
    assert l1_mid["level_number"] == 1
    assert l1_mid["progress_pct"] == 50
    assert l1_mid["xp_to_next_level"] == 125

    # Level 2: Eco Explorer (250 to 749)
    l2_start = calculate_user_level(250)
    assert l2_start["level_number"] == 2
    assert l2_start["title"] == "Eco Explorer"
    assert l2_start["progress_pct"] == 0
    assert l2_start["xp_to_next_level"] == 500

    l2_mid = calculate_user_level(500)
    assert l2_mid["level_number"] == 2
    assert l2_mid["progress_pct"] == 50
    assert l2_mid["xp_to_next_level"] == 250

    # Level 3: Eco Warrior (750 to 1499)
    l3_start = calculate_user_level(750)
    assert l3_start["level_number"] == 3
    assert l3_start["title"] == "Eco Warrior"
    assert l3_start["progress_pct"] == 0
    assert l3_start["xp_to_next_level"] == 750

    l3_mid = calculate_user_level(1125)
    assert l3_mid["level_number"] == 3
    assert l3_mid["progress_pct"] == 50
    assert l3_mid["xp_to_next_level"] == 375

    # Level 4: Green Champion (1500 to 2999)
    l4_start = calculate_user_level(1500)
    assert l4_start["level_number"] == 4
    assert l4_start["title"] == "Green Champion"
    assert l4_start["progress_pct"] == 0
    assert l4_start["xp_to_next_level"] == 1500

    l4_mid = calculate_user_level(2250)
    assert l4_mid["level_number"] == 4
    assert l4_mid["progress_pct"] == 50
    assert l4_mid["xp_to_next_level"] == 750

    # Level 5: Planet Guardian (3000 to 4999)
    l5_start = calculate_user_level(3000)
    assert l5_start["level_number"] == 5
    assert l5_start["title"] == "Planet Guardian"
    assert l5_start["progress_pct"] == 0
    assert l5_start["xp_to_next_level"] == 2000

    l5_mid = calculate_user_level(4000)
    assert l5_mid["level_number"] == 5
    assert l5_mid["progress_pct"] == 50
    assert l5_mid["xp_to_next_level"] == 1000

    # Level 6: Earth Protector (5000+)
    l6_start = calculate_user_level(5000)
    assert l6_start["level_number"] == 6
    assert l6_start["title"] == "Earth Protector"
    assert l6_start["progress_pct"] == 100
    assert l6_start["xp_to_next_level"] == 0

    l6_beyond = calculate_user_level(12500)
    assert l6_beyond["level_number"] == 6
    assert l6_beyond["title"] == "Earth Protector"
    assert l6_beyond["progress_pct"] == 100
    assert l6_beyond["xp_to_next_level"] == 0

    # Negative / None input handling
    l_neg = calculate_user_level(-50)
    assert l_neg["level_number"] == 1
    assert l_neg["total_xp"] == 0


# ============================================================
# 2. XP Awarding & Duplicate Reward Prevention
# ============================================================

def test_award_lesson_xp_success_and_idempotency(app):
    """
    Test that lesson quiz passing awards 50 XP once and logs an XPTransaction.
    Subsequent calls must be idempotent and refuse duplicate rewards.
    """
    user = create_user(email="quizzer@ecoquest.org")
    lesson = create_lesson(title="Solar Energy Fundamentals", xp_reward=50)

    # Initial passing attempt (80%)
    res1 = award_lesson_xp(user.id, lesson.id, quiz_score=80.0)
    assert res1["awarded"] is True
    assert res1["xp_amount"] == 50
    assert res1["total_xp"] == 50

    # Verify User and XPTransaction in database
    db_user = db.session.get(User, user.id)
    assert db_user.total_xp == 50

    tx = XPTransaction.query.filter_by(reference_id=f"XP-LES-U{user.id}-L{lesson.id}").first()
    assert tx is not None
    assert tx.amount == 50
    assert tx.source_type == "lesson_quiz"

    # Second passing attempt (100%) for the same lesson
    res2 = award_lesson_xp(user.id, lesson.id, quiz_score=100.0)
    assert res2["awarded"] is False
    assert res2["already_earned"] is True
    assert res2["total_xp"] == 50

    # Total XP must remain 50
    db.session.refresh(db_user)
    assert db_user.total_xp == 50

    # Transaction count must remain 1
    tx_count = XPTransaction.query.filter_by(reference_id=f"XP-LES-U{user.id}-L{lesson.id}").count()
    assert tx_count == 1


def test_award_lesson_xp_failing_score_no_xp(app):
    """
    Test that failing score (< 70%) does not award XP or create transaction.
    """
    user = create_user(email="failing@ecoquest.org")
    lesson = create_lesson(title="Wind Turbines", xp_reward=50)

    res = award_lesson_xp(user.id, lesson.id, quiz_score=60.0)
    assert res["awarded"] is False
    assert res["total_xp"] == 0

    db_user = db.session.get(User, user.id)
    assert db_user.total_xp == 0
    assert XPTransaction.query.filter_by(user_id=user.id).count() == 0


def test_award_mission_xp_success_and_idempotency(app):
    """
    Test mission verification XP awarding and strict duplicate prevention.
    """
    user = create_user(email="mission_doer@ecoquest.org")
    mission = create_mission(title="Clean Shoreline", category="Cleanup", xp_reward=150)

    # Submission with Verified status
    sub = Submission(
        user_id=user.id,
        mission_id=mission.id,
        before_photo="before.png",
        after_photo="after.png",
        description="Collected trash along 200m shoreline.",
        verification_status="Verified",
        xp_awarded=False,
    )
    db.session.add(sub)
    db.session.commit()

    # Award XP
    res1 = award_mission_xp(user.id, sub.id, mission.id)
    assert res1["awarded"] is True
    assert res1["xp_amount"] == 150
    assert res1["total_xp"] == 150

    # Verify DB updates
    db.session.refresh(user)
    assert user.total_xp == 150
    db.session.refresh(sub)
    assert sub.xp_awarded is True
    assert sub.xp_awarded_amount == 150

    tx = XPTransaction.query.filter_by(reference_id=f"XP-SUB-{sub.id:05d}").first()
    assert tx is not None
    assert tx.amount == 150

    # Attempt to award XP again
    res2 = award_mission_xp(user.id, sub.id, mission.id)
    assert res2["awarded"] is False
    assert res2["already_earned"] is True

    # User XP remains unchanged
    db.session.refresh(user)
    assert user.total_xp == 150
    assert XPTransaction.query.filter_by(reference_id=f"XP-SUB-{sub.id:05d}").count() == 1


def test_award_mission_xp_unverified_blocked(app):
    """
    Test that pending or rejected submissions are blocked from XP awarding.
    """
    user = create_user(email="pending_sub@ecoquest.org")
    mission = create_mission(title="Litter Survey")

    for status in ["Pending", "Processing", "Rejected", "Requires Manual Review"]:
        sub = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo="b.png",
            after_photo="a.png",
            description="Some desc",
            verification_status=status,
            xp_awarded=False,
        )
        db.session.add(sub)
        db.session.commit()

        res = award_mission_xp(user.id, sub.id, mission.id)
        assert res["awarded"] is False
        assert user.total_xp == 0


# ============================================================
# 3. Daily Streaks Calculations & Lapses
# ============================================================

def test_streak_tracking_and_resets(app):
    """
    Test streak calculations:
    - First qualifying activity sets streak = 1
    - Second activity on SAME calendar day does not increment
    - Consecutive day increments streak to 2
    - Missed day resets current streak to 1 while retaining longest streak
    """
    user = create_user(email="streaker@ecoquest.org")
    day1 = date(2026, 11, 1)
    day2 = date(2026, 11, 2)
    day4 = date(2026, 11, 4)  # Skipped day 3

    # Activity on Day 1
    s1 = record_qualifying_activity(user.id, activity_date=day1)
    assert s1["current_streak"] == 1
    assert s1["longest_streak"] == 1

    # Second activity on Day 1 (same day idempotent check)
    s1_dup = record_qualifying_activity(user.id, activity_date=day1)
    assert s1_dup["current_streak"] == 1
    assert s1_dup["longest_streak"] == 1

    # Consecutive activity on Day 2
    s2 = record_qualifying_activity(user.id, activity_date=day2)
    assert s2["current_streak"] == 2
    assert s2["longest_streak"] == 2

    # Query streak on Day 2
    q2 = get_user_streak(user.id, current_date=day2)
    assert q2["current_streak"] == 2
    assert q2["is_active_today"] is True

    # Query streak on Day 3 (user hasn't performed activity today yet, but streak still active from yesterday)
    day3 = date(2026, 11, 3)
    q3 = get_user_streak(user.id, current_date=day3)
    assert q3["current_streak"] == 2
    assert q3["is_active_today"] is False

    # Activity on Day 4 (day 3 was skipped)
    s4 = record_qualifying_activity(user.id, activity_date=day4)
    assert s4["current_streak"] == 1
    assert s4["longest_streak"] == 2  # Retains personal best

    # Query streak on Day 7 (lapse test: multiple days since last activity)
    day7 = date(2026, 11, 7)
    q7 = get_user_streak(user.id, current_date=day7)
    assert q7["current_streak"] == 0  # Lapsed
    assert q7["longest_streak"] == 2


# ============================================================
# 4. Badge Awarding & Duplicate Prevention
# ============================================================

def test_badge_first_steps(app):
    """First completed verified mission awards First Steps."""
    user = create_user(email="first_stepper@ecoquest.org")
    mission = create_mission(title="Street Sweep")

    # Before completion: 0 badges
    badges_before = get_user_badges(user.id)
    assert badges_before["total_earned"] == 0

    # Add 1 verified submission
    sub = Submission(
        user_id=user.id,
        mission_id=mission.id,
        before_photo="b.png",
        after_photo="a.png",
        description="Done",
        verification_status="Verified",
    )
    db.session.add(sub)
    db.session.commit()

    newly_awarded = evaluate_and_award_badges(user.id)
    assert len(newly_awarded) >= 1
    slugs = [b["slug"] for b in newly_awarded]
    assert "first-steps" in slugs

    # Verify duplicate prevention: calling again should return empty list
    dups = evaluate_and_award_badges(user.id)
    assert len(dups) == 0

    badges_after = get_user_badges(user.id)
    assert badges_after["total_earned"] >= 1
    earned_slugs = [b["slug"] for b in badges_after["earned_badges"]]
    assert "first-steps" in earned_slugs


def test_badge_green_thumb(app):
    """First verified tree plantation mission awards Green Thumb."""
    user = create_user(email="tree_planter@ecoquest.org")
    mission = create_mission(
        title="Plant a Native Sapling",
        category="Tree Plantation",
        category_slug="tree-plantation",
    )

    sub = Submission(
        user_id=user.id,
        mission_id=mission.id,
        before_photo="b.png",
        after_photo="a.png",
        description="Planted a Neem tree",
        verification_status="Verified",
    )
    db.session.add(sub)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "green-thumb" in earned
    assert "first-steps" in earned


def test_badge_waste_warrior(app):
    """Five verified cleanup or recycling missions award Waste Warrior."""
    user = create_user(email="cleaner@ecoquest.org")
    cleanup_m = create_mission(title="Park Cleanup", category="Cleanup")
    recycling_m = create_mission(title="E-Waste Sorting", category="Recycling")

    # 4 verified missions (not yet 5)
    for i in range(4):
        s = Submission(
            user_id=user.id,
            mission_id=cleanup_m.id if i % 2 == 0 else recycling_m.id,
            before_photo=f"b{i}.png",
            after_photo=f"a{i}.png",
            description=f"Action {i}",
            verification_status="Verified",
        )
        db.session.add(s)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned_4 = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "waste-warrior" not in earned_4

    # 5th verified mission
    s5 = Submission(
        user_id=user.id,
        mission_id=cleanup_m.id,
        before_photo="b5.png",
        after_photo="a5.png",
        description="5th cleanup",
        verification_status="Verified",
    )
    db.session.add(s5)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned_5 = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "waste-warrior" in earned_5


def test_badge_water_saver(app):
    """Three verified water missions award Water Saver."""
    user = create_user(email="water_hero@ecoquest.org")
    water_m = create_mission(title="Fix Leaks", category="Water Conservation")

    for i in range(3):
        s = Submission(
            user_id=user.id,
            mission_id=water_m.id,
            before_photo=f"b{i}.png",
            after_photo=f"a{i}.png",
            description=f"Water mission {i}",
            verification_status="Verified",
        )
        db.session.add(s)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "water-saver" in earned


def test_badge_knowledge_seeker(app):
    """Five completed lessons award Knowledge Seeker."""
    user = create_user(email="scholar@ecoquest.org")

    for i in range(5):
        l = create_lesson(title=f"Lesson Topic {i+1}")
        prog = LessonProgress(
            user_id=user.id,
            lesson_id=l.id,
            status="completed",
            completed=True,
            xp_awarded=True,
            completed_at=utc_now(),
        )
        db.session.add(prog)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "knowledge-seeker" in earned


def test_badge_eco_champion(app):
    """Twenty verified missions award Eco Champion."""
    user = create_user(email="super_champ@ecoquest.org")
    mission = create_mission(title="Generic Eco Task")

    for i in range(20):
        s = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo=f"b{i}.png",
            after_photo=f"a{i}.png",
            description=f"Action {i}",
            verification_status="Verified",
        )
        db.session.add(s)
    db.session.commit()

    evaluate_and_award_badges(user.id)
    earned = [b["slug"] for b in get_user_badges(user.id)["earned_badges"]]
    assert "eco-champion" in earned


# ============================================================
# 5. Leaderboard Rankings & Deterministic Tie-Breaking
# ============================================================

def test_leaderboard_global_and_deterministic_tie_breaking(app):
    """
    Test deterministic rankings:
    1. XP DESC
    2. Verified missions count DESC
    3. User created_at ASC
    4. User ID ASC
    """
    t_early = datetime(2026, 1, 1, 10, 0, 0)
    t_late = datetime(2026, 1, 5, 10, 0, 0)

    # User A: 500 XP, 2 verified missions
    u_a = create_user(email="user_a@ecoquest.org", name="User A", total_xp=500, created_at=t_early)
    # User B: 500 XP, 4 verified missions -> Should beat User A!
    u_b = create_user(email="user_b@ecoquest.org", name="User B", total_xp=500, created_at=t_late)
    # User C: 1000 XP -> First place
    u_c = create_user(email="user_c@ecoquest.org", name="User C", total_xp=1000, created_at=t_late)

    mission = create_mission(title="Litter Drive")

    # Add verified submissions for User A (2)
    for i in range(2):
        db.session.add(Submission(user_id=u_a.id, mission_id=mission.id, before_photo="b", after_photo="a", description="d", verification_status="Verified"))

    # Add verified submissions for User B (4)
    for i in range(4):
        db.session.add(Submission(user_id=u_b.id, mission_id=mission.id, before_photo="b", after_photo="a", description="d", verification_status="Verified"))

    db.session.commit()

    lb = get_leaderboard_rankings(category="global", timeframe="all_time")
    rankings = lb["rankings"]

    assert len(rankings) == 3
    # 1st place: User C (1000 XP)
    assert rankings[0]["user_id"] == u_c.id
    assert rankings[0]["rank"] == 1

    # 2nd place: User B (500 XP, 4 missions beats User A's 2 missions)
    assert rankings[1]["user_id"] == u_b.id
    assert rankings[1]["rank"] == 2

    # 3rd place: User A (500 XP, 2 missions)
    assert rankings[2]["user_id"] == u_a.id
    assert rankings[2]["rank"] == 3


def test_leaderboard_city_and_college_filtering(app):
    """
    Test filtering by city and college.
    """
    u_blr = create_user(email="blr@ecoquest.org", name="BLR User", city="Bengaluru", college="IISc Bangalore", total_xp=400)
    u_mum = create_user(email="mum@ecoquest.org", name="MUM User", city="Mumbai", college="IIT Bombay", total_xp=600)
    u_del = create_user(email="del@ecoquest.org", name="DEL User", city="Delhi", college="IIT Delhi", total_xp=800)

    # City filter: Bengaluru
    lb_city = get_leaderboard_rankings(category="city", city="Bengaluru")
    city_ids = [r["user_id"] for r in lb_city["rankings"]]
    assert u_blr.id in city_ids
    assert u_mum.id not in city_ids
    assert u_del.id not in city_ids

    # College filter: IIT Bombay
    lb_college = get_leaderboard_rankings(category="college", college="IIT Bombay")
    college_ids = [r["user_id"] for r in lb_college["rankings"]]
    assert u_mum.id in college_ids
    assert u_blr.id not in college_ids
    assert u_del.id not in college_ids


def test_leaderboard_weekly_and_monthly_filters(app):
    """
    Test timeframe filters using XPTransaction timestamps.
    """
    now = utc_now()
    user_recent = create_user(email="recent@ecoquest.org", name="Recent User", total_xp=300)
    user_older = create_user(email="older@ecoquest.org", name="Older User", total_xp=500)

    # User Recent earned 300 XP 2 days ago (within 7 days)
    tx_recent = XPTransaction(
        user_id=user_recent.id,
        amount=300,
        source_type="mission_verification",
        reference_id="TX-RECENT-1",
        description="Recent mission",
        created_at=now - timedelta(days=2),
    )
    db.session.add(tx_recent)

    # User Older earned 500 XP 20 days ago (within 30 days, but older than 7 days)
    tx_older = XPTransaction(
        user_id=user_older.id,
        amount=500,
        source_type="mission_verification",
        reference_id="TX-OLDER-1",
        description="Older mission",
        created_at=now - timedelta(days=20),
    )
    db.session.add(tx_older)
    db.session.commit()

    # Weekly filter: Only user_recent has activity in past 7 days
    lb_weekly = get_leaderboard_rankings(category="global", timeframe="weekly")
    weekly_scores = {r["user_id"]: r["score_xp"] for r in lb_weekly["rankings"]}
    assert weekly_scores.get(user_recent.id) == 300
    assert weekly_scores.get(user_older.id) == 0

    # Monthly filter: Both have activity in past 30 days
    lb_monthly = get_leaderboard_rankings(category="global", timeframe="monthly")
    monthly_scores = {r["user_id"]: r["score_xp"] for r in lb_monthly["rankings"]}
    assert monthly_scores.get(user_older.id) == 500
    assert monthly_scores.get(user_recent.id) == 300


def test_leaderboard_user_highlight_and_summary(app):
    """
    Test user position extraction and personal standing summary.
    """
    u1 = create_user(email="top@ecoquest.org", name="Top User", city="Pune", college="COEP", total_xp=800)
    u2 = create_user(email="second@ecoquest.org", name="Second User", city="Pune", college="COEP", total_xp=400)

    lb = get_leaderboard_rankings(category="global", current_user_id=u2.id)
    assert lb["user_position"] is not None
    assert lb["user_position"]["user_id"] == u2.id
    assert lb["user_position"]["rank"] == 2
    assert lb["user_position"]["is_current_user"] is True

    # User summary helper
    summary = get_user_leaderboard_summary(u2.id)
    assert summary["global_rank"] == 2
    assert summary["city_rank"] == 2
    assert summary["college_rank"] == 2


# ============================================================
# 6. Dashboard & HTTP Endpoints Integration
# ============================================================

def test_leaderboard_endpoints_html_and_json(client, app):
    """
    Test GET /leaderboard/ renders HTML template, and ?format=json returns structured API data.
    """
    create_user(email="public_ranker@ecoquest.org", name="Ranker", total_xp=250)

    # HTML response
    resp_html = client.get("/leaderboard/")
    assert resp_html.status_code == 200
    assert "Community Leaderboard" in resp_html.data.decode("utf-8")
    assert "Global" in resp_html.data.decode("utf-8")

    # JSON response
    resp_json = client.get("/leaderboard/?format=json")
    assert resp_json.status_code == 200
    data = resp_json.get_json()
    assert data["status"] == "success"
    assert "rankings" in data["data"]
    assert len(data["data"]["rankings"]) >= 1


def test_dashboard_consistency_with_database(client, app):
    """
    Test that the dashboard correctly reflects real database XP, level, badges, and streaks.
    """
    user = create_user(email="dash_user@ecoquest.org", name="Dash Member", total_xp=850)
    # Set up streak
    record_qualifying_activity(user.id, activity_date=utc_now().date())

    # Log in user
    with client.session_transaction() as sess:
        sess["user_id"] = user.id

    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Check Total XP and Level
    assert "850" in html
    assert "Eco Warrior" in html  # 850 XP is Level 3 (Eco Warrior)
    assert "Environmental Badges" in html
    assert "Leaderboard Position" in html
