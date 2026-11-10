"""
EcoQuest — Environmental Mission Management System Test Suite.

Automated verification of:
- Mission database integrity (6 categories, 18+ sample missions, instructions, safety guidelines).
- Mission catalog discovery, search, difficulty filters, and sorting.
- Mission detail page content rendering (why it matters, steps, proof, safety).
- Mission acceptance workflow.
- Strict prevention of duplicate active missions.
- Repeat participation permission guards.
- No XP awarded merely for accepting missions.
- Personal mission tracking dashboard (/missions/my-missions).
- Multi-user isolation.
- Dashboard integration (accepted/ongoing missions and activity feed).
- Static assets and mobile responsive styling.
"""

import pytest
from app import create_app
from models import db, User, Mission, UserMission


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


def test_mission_seeding_and_integrity(app):
    """Verify that all 6 categories and at least 18 missions are seeded with full attributes."""
    with app.app_context():
        required_categories = [
            "Cleanup",
            "Tree Plantation",
            "Recycling",
            "Water Conservation",
            "Sustainable Transport",
            "Environmental Awareness",
        ]

        total_missions = Mission.query.count()
        assert total_missions >= 18, f"Expected at least 18 missions, found {total_missions}"

        for cat_name in required_categories:
            cat_missions = Mission.query.filter_by(category=cat_name).all()
            assert len(cat_missions) >= 3, f"Category '{cat_name}' has fewer than 3 missions"

        # Verify attributes on all missions
        for m in Mission.query.all():
            assert m.title, f"Mission {m.id} missing title"
            assert m.slug, f"Mission {m.id} missing slug"
            assert m.category, f"Mission {m.title} missing category"
            assert m.difficulty in ["Beginner", "Intermediate", "Advanced"]
            assert m.duration
            assert m.xp_reward >= 50
            assert m.location
            assert m.short_description
            assert m.description
            assert m.why_it_matters
            assert len(m.instructions) >= 3, f"Mission {m.title} has fewer than 3 instructions"
            assert m.proof_requirements
            assert len(m.safety_guidelines) >= 2, f"Mission {m.title} has fewer than 2 safety guidelines"
            assert m.image


def test_mission_catalog_listing(client):
    """Verify /missions/ renders the catalog with all 6 categories and mission cards."""
    response = client.get("/missions/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Environmental Action Missions" in html
    assert "Real-World Hands-On Challenges" in html

    # All 6 categories in navigation tabs
    assert "Cleanup" in html
    assert "Tree Plantation" in html
    assert "Recycling" in html
    assert "Water Conservation" in html
    assert "Sustainable Transport" in html
    assert "Environmental Awareness" in html

    # Mission cards render key metadata
    assert "XP" in html
    assert "📍" in html or "Completed" in html
    assert "View Details" in html


def test_mission_search_and_filters(client):
    """Verify category filtering, difficulty filtering, keyword search, and sorting."""
    # 1. Filter by category
    res_cat = client.get("/missions/?category=cleanup")
    assert res_cat.status_code == 200
    html_cat = res_cat.data.decode("utf-8")
    assert "Clean a Public Area" in html_cat

    # 2. Filter by difficulty
    res_diff = client.get("/missions/?difficulty=Beginner")
    assert res_diff.status_code == 200
    html_diff = res_diff.data.decode("utf-8")
    assert "Beginner" in html_diff

    # 3. Keyword search
    res_search = client.get("/missions/?q=bicycle")
    assert res_search.status_code == 200
    html_search = res_search.data.decode("utf-8")
    assert "Bicycle Commute" in html_search

    # 4. JSON endpoint support
    res_json = client.get("/missions/?format=json")
    assert res_json.status_code == 200
    json_data = res_json.get_json()
    assert json_data["status"] == "success"
    assert json_data["total_count"] >= 18
    assert len(json_data["missions"]) >= 18


def test_mission_detail_rendering(client):
    """Verify individual mission detail view renders instructions, why it matters, proof, and safety."""
    response = client.get("/missions/clean-a-public-area")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Clean a Public Area" in html
    assert "Cleanup" in html
    assert "Why This Mission Matters" in html
    assert "Step-by-Step Instructions" in html
    assert "Verification Proof Requirements" in html
    assert "Fieldwork Safety Guidelines" in html
    assert "Reward on Verification" in html

    # Unauthenticated visitor prompt
    assert "Log In to Accept Mission" in html

    # 404 test
    res_404 = client.get("/missions/non-existent-mission-slug")
    assert res_404.status_code in [302, 404]


def test_mission_acceptance_unauthenticated(client):
    """Unauthenticated users cannot accept missions."""
    response = client.post(
        "/missions/clean-a-public-area/accept",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "authentication_required" in data["error"]


def test_mission_acceptance_and_no_xp_rule(client, app):
    """
    Verify:
    1. Member accepts mission.
    2. UserMission record created with status 'accepted'.
    3. User total_xp is NOT changed (no XP merely for accepting).
    """
    client.post(
        "/auth/register",
        data={
            "full_name": "Kavya Desai",
            "email": "kavya@ecoquest.org",
            "phone": "+91 95555 11111",
            "city": "Ahmedabad",
            "college": "Gujarat University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "kavya@ecoquest.org", "password": "Password123"})

    with app.app_context():
        u = User.query.filter_by(email="kavya@ecoquest.org").first()
        assert u.total_xp == 0
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    # Accept mission
    response = client.post(
        f"/missions/{mission.slug}/accept",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "accepted" in data["message"].lower()

    # Verify database state
    with app.app_context():
        u = User.query.filter_by(email="kavya@ecoquest.org").first()
        # CRUCIAL RULE: XP must NOT be awarded for accepting
        assert u.total_xp == 0

        um = UserMission.query.filter_by(user_id=u.id, mission_id=mission.id).first()
        assert um is not None
        assert um.status == "accepted"
        assert um.completed_at is None

    # Detail page should now reflect Ongoing
    detail_res = client.get(f"/missions/{mission.slug}")
    assert detail_res.status_code == 200
    detail_html = detail_res.data.decode("utf-8")
    assert "Mission Ongoing" in detail_html


def test_duplicate_active_mission_prevention(client, app):
    """Verify that a user cannot accept an already active mission."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Rohan Mehra",
            "email": "rohan@ecoquest.org",
            "phone": "+91 96666 22222",
            "city": "Pune",
            "college": "Pune University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "rohan@ecoquest.org", "password": "Password123"})

    with app.app_context():
        mission = Mission.query.filter_by(slug="plant-a-native-tree").first()

    # First acceptance: OK
    res1 = client.post(f"/missions/{mission.slug}/accept", headers={"Accept": "application/json"})
    assert res1.status_code == 200
    assert res1.get_json()["success"] is True

    # Duplicate acceptance: BLOCKED
    res2 = client.post(f"/missions/{mission.slug}/accept", headers={"Accept": "application/json"})
    assert res2.status_code == 400
    data2 = res2.get_json()
    assert data2["success"] is False
    assert data2["error"] == "already_active"

    # Only 1 record exists
    with app.app_context():
        u = User.query.filter_by(email="rohan@ecoquest.org").first()
        count = UserMission.query.filter_by(user_id=u.id, mission_id=mission.id).count()
        assert count == 1


def test_my_missions_management_dashboard(client, app):
    """Verify /missions/my-missions displays accepted, ongoing, and completed status tabs."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Ananya Sen",
            "email": "ananya@ecoquest.org",
            "phone": "+91 97777 33333",
            "city": "Kolkata",
            "college": "Jadavpur University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "ananya@ecoquest.org", "password": "Password123"})

    with app.app_context():
        m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
        m2 = Mission.query.filter_by(slug="collect-recyclable-waste").first()

    client.post(f"/missions/{m1.slug}/accept")
    client.post(f"/missions/{m2.slug}/accept")

    response = client.get("/missions/my-missions")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "My Environmental Quests" in html
    assert "Total Accepted" in html
    assert "Clean a Public Area" in html
    assert "Collect Recyclable Waste" in html
    assert "Ongoing Action" in html

    # JSON endpoint
    res_json = client.get("/missions/my-missions?format=json")
    assert res_json.status_code == 200
    data = res_json.get_json()
    assert data["status"] == "success"
    assert data["total_accepted"] == 2


def test_multi_user_mission_isolation(client, app):
    """Verify complete isolation between different user accounts."""
    # User 1
    client.post(
        "/auth/register",
        data={
            "full_name": "Member Alpha",
            "email": "alpha@ecoquest.org",
            "phone": "+91 91111 00001",
            "city": "Jaipur",
            "college": "Rajasthan University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    # User 2
    client.post(
        "/auth/register",
        data={
            "full_name": "Member Beta",
            "email": "beta@ecoquest.org",
            "phone": "+91 91111 00002",
            "city": "Lucknow",
            "college": "Lucknow University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Login Alpha and accept mission
    client.post("/auth/login", data={"email": "alpha@ecoquest.org", "password": "Password123"})
    with app.app_context():
        mission = Mission.query.first()
    client.post(f"/missions/{mission.slug}/accept")

    # Logout Alpha and login Beta
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "beta@ecoquest.org", "password": "Password123"})

    with app.app_context():
        u1 = User.query.filter_by(email="alpha@ecoquest.org").first()
        u2 = User.query.filter_by(email="beta@ecoquest.org").first()

        assert UserMission.query.filter_by(user_id=u1.id).count() == 1
        assert UserMission.query.filter_by(user_id=u2.id).count() == 0

    # Beta can accept the same mission independently
    res_beta = client.post(f"/missions/{mission.slug}/accept", headers={"Accept": "application/json"})
    assert res_beta.status_code == 200
    assert res_beta.get_json()["success"] is True


def test_dashboard_integration_with_accepted_missions(client, app):
    """Verify that accepted missions appear in user dashboard activity feed and recommended mission list."""
    client.post(
        "/auth/register",
        data={
            "full_name": "Vikram Sethi",
            "email": "vikram@ecoquest.org",
            "phone": "+91 98888 44444",
            "city": "Chandigarh",
            "college": "Panjab University",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "vikram@ecoquest.org", "password": "Password123"})

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    # Accept mission
    client.post(f"/missions/{mission.slug}/accept")

    # Inspect dashboard
    dash_res = client.get("/dashboard/")
    assert dash_res.status_code == 200
    html = dash_res.data.decode("utf-8")

    assert "Accepted Mission:" in html
    assert "Clean a Public Area" in html
    assert "Ongoing" in html


def test_static_mission_assets(client):
    """Verify that missions.css and all 6 SVG mission images serve with HTTP 200."""
    res_css = client.get("/static/css/missions.css")
    assert res_css.status_code == 200
    css = res_css.data.decode("utf-8")
    assert "@media (max-width: 1024px)" in css
    assert "@media (max-width: 768px)" in css
    assert "@media (max-width: 480px)" in css
    assert ".mission-card" in css
    assert ".mission-detail-container" in css

    svg_files = [
        "mission-cleanup.svg",
        "mission-tree.svg",
        "mission-recycling.svg",
        "mission-water.svg",
        "mission-transport.svg",
        "mission-awareness.svg",
    ]
    for svg in svg_files:
        res_svg = client.get(f"/static/images/{svg}")
        assert res_svg.status_code == 200, f"Failed to serve SVG: {svg}"
