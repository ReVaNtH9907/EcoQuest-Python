"""
EcoQuest — Learning Academy Test Suite.

Automated verification of:
- Curriculum database integrity (8 categories, 16+ lessons, questions, options, explanations).
- Lesson discovery and catalog browsing.
- Category filtering (HTML and JSON).
- Full lesson content rendering (introduction, sections, facts, takeaways, quiz).
- Quiz evaluation with passing (>= 70%) and failing scores.
- Centralized XP service integration (+50 XP awarded once on passing).
- Duplicate XP prevention upon retakes.
- Lesson progress and attempt persistence.
- Multi-user isolation.
- Dashboard integration (lessons completed, learning XP, and recent activity stream).
- Responsive CSS and JavaScript assets.
"""

import pytest
from app import create_app
from models import (
    db,
    User,
    LessonCategory,
    Lesson,
    QuizQuestion,
    QuizOption,
    LessonProgress,
    QuizAttempt,
)


@pytest.fixture
def app():
    """Create testing application with SQLite in-memory database."""
    test_app = create_app("testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


def test_curriculum_seeding_and_integrity(app):
    """Verify that curriculum seeds all 8 required categories and at least 16 lessons with full quiz questions."""
    with app.app_context():
        required_categories = [
            "Climate Change",
            "Waste Management",
            "Water Conservation",
            "Biodiversity",
            "Renewable Energy",
            "Sustainable Living",
            "Pollution",
            "Forest Conservation",
        ]

        categories = LessonCategory.query.all()
        assert len(categories) == 8, f"Expected 8 categories, found {len(categories)}"

        cat_names = [c.name for c in categories]
        for req in required_categories:
            assert req in cat_names, f"Missing required category: {req}"

        # Verify lessons: at least 2 complete lessons per category
        total_lessons = Lesson.query.count()
        assert total_lessons >= 16, f"Expected at least 16 lessons, found {total_lessons}"

        for cat in categories:
            assert len(cat.lessons) >= 2, f"Category '{cat.name}' has fewer than 2 lessons"

        # Verify lesson structure and quiz integrity
        for lesson in Lesson.query.all():
            assert lesson.title, f"Lesson {lesson.id} missing title"
            assert lesson.slug, f"Lesson {lesson.id} missing slug"
            assert lesson.summary, f"Lesson {lesson.title} missing summary"
            assert lesson.introduction, f"Lesson {lesson.title} missing introduction"
            assert len(lesson.content_sections) >= 2, f"Lesson {lesson.title} missing content sections"
            assert len(lesson.important_facts) >= 2, f"Lesson {lesson.title} missing facts"
            assert len(lesson.key_takeaways) >= 2, f"Lesson {lesson.title} missing takeaways"
            assert lesson.xp_reward == 50

            # Quizzes: 3-4 questions, 4 options each, exactly 1 correct option
            questions = lesson.questions
            assert len(questions) >= 3, f"Lesson {lesson.title} has fewer than 3 questions"
            for q in questions:
                assert q.question_text
                assert q.explanation
                assert len(q.options) == 4, f"Question '{q.question_text}' does not have 4 options"
                correct_options = [o for o in q.options if o.is_correct]
                assert len(correct_options) == 1, (
                    f"Question '{q.question_text}' must have exactly 1 correct option, found {len(correct_options)}"
                )


def test_learning_discovery_catalog_page(client):
    """Verify /learning/ renders the catalog with all 8 categories and lesson cards."""
    response = client.get("/learning/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "EcoQuest Learning Academy" in html
    assert "Science-Backed Environmental Curriculum" in html

    # Check that all 8 categories appear in the filter tabs
    assert "Climate Change" in html
    assert "Waste Management" in html
    assert "Water Conservation" in html
    assert "Biodiversity" in html
    assert "Renewable Energy" in html
    assert "Sustainable Living" in html
    assert "Pollution" in html
    assert "Forest Conservation" in html

    # Check lesson card metadata
    assert "50 XP" in html
    assert "mins" in html
    assert "Questions" in html
    assert "70% to Pass" in html


def test_learning_category_filtering(client):
    """Verify category filtering via query parameter and JSON endpoint."""
    # 1. Filter HTML by climate-change
    res_cc = client.get("/learning/?category=climate-change")
    assert res_cc.status_code == 200
    html_cc = res_cc.data.decode("utf-8")
    assert "Greenhouse Effect" in html_cc

    # 2. Filter HTML by waste-management
    res_wm = client.get("/learning/?category=waste-management")
    assert res_wm.status_code == 200
    html_wm = res_wm.data.decode("utf-8")
    assert "Circular Economy" in html_wm or "Composting" in html_wm

    # 3. JSON endpoint support
    res_json = client.get("/learning/?format=json")
    assert res_json.status_code == 200
    json_data = res_json.get_json()
    assert json_data["status"] == "success"
    assert len(json_data["categories"]) == 8
    assert len(json_data["lessons"]) >= 16


def test_individual_lesson_rendering(client):
    """Verify detailed lesson content page renders introduction, sections, facts, takeaways, and quiz."""
    response = client.get("/learning/greenhouse-effect-global-dynamics")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "The Greenhouse Effect and Global Climate Dynamics" in html
    assert "Climate Change" in html
    assert "50 XP" in html
    assert "Radiative Balance" in html
    assert "Key Environmental Facts" in html
    assert "Actionable Key Takeaways" in html
    assert "Lesson Quiz" in html
    assert "70% or higher" in html

    # Unauthenticated visitor prompt
    assert "Sign in to take the quiz and earn 50 XP" in html

    # Test nonexistent lesson
    res_404 = client.get("/learning/non-existent-lesson-slug")
    assert res_404.status_code in [302, 404]


def test_quiz_unauthenticated_blocked(client):
    """Unauthenticated users cannot submit quiz answers for XP."""
    response = client.post(
        "/learning/greenhouse-effect-global-dynamics/quiz",
        json={"answers": {"1": 1}},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "Authentication required" in data["error"]


def test_quiz_failing_and_passing_flow(client, app):
    """
    Test complete lifecycle:
    1. Register & login user.
    2. Submit failing answers (< 70%). Verify: no XP, progress marked in_progress.
    3. Retake with passing answers (>= 70%). Verify: 50 XP awarded, progress marked completed.
    4. Retake with passing answers again. Verify: NO duplicate XP awarded.
    """
    # 1. Register and login
    client.post(
        "/auth/register",
        data={
            "full_name": "Aarav Patel",
            "email": "aarav@ecoquest.org",
            "phone": "+91 91234 56789",
            "city": "Mumbai",
            "college": "IIT Bombay",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "aarav@ecoquest.org", "password": "Password123"})

    with app.app_context():
        user = User.query.filter_by(email="aarav@ecoquest.org").first()
        assert user.total_xp == 0

        lesson = Lesson.query.filter_by(slug="greenhouse-effect-global-dynamics").first()
        questions = lesson.questions
        assert len(questions) >= 3

        # Prepare 100% incorrect answers
        wrong_answers = {}
        correct_answers = {}
        for q in questions:
            for opt in q.options:
                if not opt.is_correct:
                    wrong_answers[str(q.id)] = opt.id
                    break
            for opt in q.options:
                if opt.is_correct:
                    correct_answers[str(q.id)] = opt.id
                    break

    # 2. Submit FAILING quiz (0% score)
    res_fail = client.post(
        f"/learning/{lesson.slug}/quiz",
        json={"answers": wrong_answers},
        headers={"Accept": "application/json"},
    )
    assert res_fail.status_code == 200
    fail_data = res_fail.get_json()
    assert fail_data["success"] is True
    assert fail_data["passed"] is False
    assert fail_data["score"] < 70.0
    assert fail_data["xp_awarded"] is False
    assert fail_data["total_xp"] == 0

    with app.app_context():
        u = User.query.filter_by(email="aarav@ecoquest.org").first()
        assert u.total_xp == 0
        progress = LessonProgress.query.filter_by(user_id=u.id, lesson_id=lesson.id).first()
        assert progress is not None
        assert progress.status == "in_progress"
        assert progress.completed is False
        assert progress.xp_awarded is False

        # Attempt log exists
        attempt = QuizAttempt.query.filter_by(user_id=u.id, lesson_id=lesson.id).first()
        assert attempt is not None
        assert attempt.passed is False

    # 3. Retake with PASSING quiz (100% score)
    res_pass = client.post(
        f"/learning/{lesson.slug}/quiz",
        json={"answers": correct_answers},
        headers={"Accept": "application/json"},
    )
    assert res_pass.status_code == 200
    pass_data = res_pass.get_json()
    assert pass_data["success"] is True
    assert pass_data["passed"] is True
    assert pass_data["score"] == 100.0
    assert pass_data["xp_awarded"] is True
    assert pass_data["xp_amount"] == 50
    assert pass_data["total_xp"] == 50

    with app.app_context():
        u = User.query.filter_by(email="aarav@ecoquest.org").first()
        assert u.total_xp == 50
        progress = LessonProgress.query.filter_by(user_id=u.id, lesson_id=lesson.id).first()
        assert progress.status == "completed"
        assert progress.completed is True
        assert progress.xp_awarded is True
        assert progress.highest_score == 100.0

    # 4. DUPLICATE XP PREVENTION: Retake passing quiz again
    res_dup = client.post(
        f"/learning/{lesson.slug}/quiz",
        json={"answers": correct_answers},
        headers={"Accept": "application/json"},
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.get_json()
    assert dup_data["success"] is True
    assert dup_data["passed"] is True
    assert dup_data["xp_awarded"] is False  # NO duplicate XP!
    assert dup_data["already_earned"] is True
    assert dup_data["total_xp"] == 50  # Unchanged!

    with app.app_context():
        u = User.query.filter_by(email="aarav@ecoquest.org").first()
        assert u.total_xp == 50  # Must remain exactly 50


def test_multi_user_isolation(client, app):
    """Verify that multiple users have completely isolated progress and XP."""
    # User 1
    client.post(
        "/auth/register",
        data={
            "full_name": "User One",
            "email": "user1@ecoquest.org",
            "phone": "+91 90000 00001",
            "city": "Delhi",
            "college": "Delhi University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    # User 2
    client.post(
        "/auth/register",
        data={
            "full_name": "User Two",
            "email": "user2@ecoquest.org",
            "phone": "+91 90000 00002",
            "city": "Chennai",
            "college": "IIT Madras",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Login User 1 and complete lesson 1
    client.post("/auth/login", data={"email": "user1@ecoquest.org", "password": "Password123"})
    with app.app_context():
        lesson = Lesson.query.first()
        correct_answers = {
            str(q.id): next(o.id for o in q.options if o.is_correct)
            for q in lesson.questions
        }

    client.post(
        f"/learning/{lesson.slug}/quiz",
        json={"answers": correct_answers},
        headers={"Accept": "application/json"},
    )

    # Logout User 1 and login User 2
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "user2@ecoquest.org", "password": "Password123"})

    with app.app_context():
        u1 = User.query.filter_by(email="user1@ecoquest.org").first()
        u2 = User.query.filter_by(email="user2@ecoquest.org").first()

        assert u1.total_xp == 50
        assert u2.total_xp == 0  # User 2 untouched

        p2 = LessonProgress.query.filter_by(user_id=u2.id, lesson_id=lesson.id).first()
        assert p2 is None or p2.completed is False


def test_dashboard_integration_with_learning(client, app):
    """Verify that completed lessons and XP update the user dashboard and recent activities dynamically."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Priya Nair",
            "email": "priya@ecoquest.org",
            "phone": "+91 94444 55555",
            "city": "Kochi",
            "college": "Cochin University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "priya@ecoquest.org", "password": "Password123"})

    # Check dashboard before completing any lesson
    dash_res1 = client.get("/dashboard/")
    assert dash_res1.status_code == 200
    html1 = dash_res1.data.decode("utf-8")
    assert "0" in html1  # 0 XP
    assert "No activity recorded yet" in html1

    # Complete a lesson with 100% quiz score
    with app.app_context():
        lesson = Lesson.query.filter_by(slug="circular-economy-beyond-landfills").first()
        correct_answers = {
            str(q.id): next(o.id for o in q.options if o.is_correct)
            for q in lesson.questions
        }

    client.post(
        f"/learning/{lesson.slug}/quiz",
        json={"answers": correct_answers},
        headers={"Accept": "application/json"},
    )

    # Check dashboard after completing the lesson
    dash_res2 = client.get("/dashboard/")
    assert dash_res2.status_code == 200
    html2 = dash_res2.data.decode("utf-8")

    # 1. Total XP should reflect 50 XP
    assert "50" in html2
    # 2. Lessons completed should reflect 1
    assert "1" in html2
    # 3. Recent activity should now show the completed lesson with badge
    assert "Mastered Lesson:" in html2
    assert "Circular Economy" in html2
    assert "+50 XP" in html2


def test_learning_progress_api(client):
    """Verify /learning/progress JSON endpoint returns accurate progress metrics."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Siddharth Rao",
            "email": "sid@ecoquest.org",
            "phone": "+91 97777 88888",
            "city": "Hyderabad",
            "college": "IIIT Hyderabad",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "sid@ecoquest.org", "password": "Password123"})

    response = client.get("/learning/progress")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "learning_progress" in data
    assert "xp_summary" in data
    prog = data["learning_progress"]
    assert prog["total_lessons"] >= 16
    assert prog["lessons_completed"] == 0
    assert len(prog["category_progress"]) == 8


def test_static_learning_assets(client):
    """Verify that CSS and JS static files exist and serve with HTTP 200."""
    res_css = client.get("/static/css/learning.css")
    assert res_css.status_code == 200
    css_content = res_css.data.decode("utf-8")
    assert "@media (max-width: 1024px)" in css_content
    assert "@media (max-width: 768px)" in css_content
    assert "@media (max-width: 480px)" in css_content
    assert ".lesson-card" in css_content
    assert ".quiz-question-card" in css_content

    res_js = client.get("/static/js/learning.js")
    assert res_js.status_code == 200
    js_content = res_js.data.decode("utf-8")
    assert "initCategoryFiltering" in js_content
    assert "initQuizInteractivity" in js_content
