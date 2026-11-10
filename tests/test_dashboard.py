"""
EcoQuest — User Dashboard Verification Test Suite.

Verifies:
  1. Access control: unauthenticated users redirected to login
  2. Authenticated access: logged-in user can access dashboard with HTTP 200
  3. Dashboard header: user full name, avatar, current date, motivational message
  4. Progress overview: 5 stat cards (Total XP, Level, Missions, Lessons, Streak)
  5. Environmental impact: 4 metrics (Waste, Trees, Areas, Volunteer hours)
  6. Recommended missions: sample mission cards with category, difficulty, XP
  7. Learning progress: module status, percentage, Continue Learning button
  8. Recent activity: friendly empty state for new accounts
  9. User separation: User A and User B see their own personalized information
  10. Navigation links: Home, Learn, Missions, Impact, Leaderboard, Profile, Logout
  11. Responsive CSS rules: breakpoints for tablet and mobile
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db, User


@pytest.fixture
def app():
    """Create and configure a testing Flask app instance."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


def test_dashboard_unauthenticated_redirect(client):
    """Unauthenticated access to /dashboard/ must redirect to login."""
    response = client.get("/dashboard/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_dashboard_authenticated_access(client, app):
    """Logged in user can access /dashboard/ with HTTP 200 and see personalized content."""
    # Register and login user
    client.post(
        "/auth/register",
        data={
            "full_name": "Rahul Sharma",
            "email": "rahul@ecoquest.org",
            "phone": "+91 98765 43210",
            "city": "Bengaluru",
            "college": "Indian Institute of Science",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": "rahul@ecoquest.org", "password": "Password123"})

    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # 1. Header checks
    assert "Welcome back, Rahul Sharma!" in html
    assert "Indian Institute of Science" in html
    assert "Bengaluru" in html
    assert "default-avatar.svg" in html
    assert "📅" in html or "202" in html  # current date check

    # 2. Progress Overview (5 stat cards)
    assert "Total XP" in html
    assert "Current Level" in html
    assert "Missions" in html
    assert "Lessons" in html
    assert "Streak" in html

    # 3. Environmental Impact (4 metrics with honest zero values)
    assert "Waste Collected" in html
    assert "0.0 kg" in html or "0 kg" in html
    assert "Trees Planted" in html
    assert "Areas Cleaned" in html
    assert "Volunteer Hours" in html

    # 4. Recommended Missions
    assert "Recommended Missions" in html
    assert "Clean a Public Area" in html
    assert "Plant a Native Tree" in html
    assert "Collect Recyclable Waste" in html
    assert "150 XP" in html
    assert "250 XP" in html
    assert "View Mission" in html

    # 5. Learning Progress
    assert "Learning Progress" in html
    assert "Continue Learning" in html
    assert "lessons completed" in html

    # 6. Recent Activity (Friendly empty state)
    assert "Recent Activity" in html
    assert "No activity recorded yet" in html
    assert "Start First Mission" in html

    # 7. Navigation links present
    assert 'href="/"' in html or ">Home<" in html
    assert "/learning/" in html
    assert "/missions/" in html
    assert "#impact" in html
    assert "/leaderboard/" in html
    assert "/profile/" in html
    assert "/auth/logout" in html


def test_user_data_separation(client, app):
    """Ensure different members see their own personalized information."""
    # Register User A
    client.post(
        "/auth/register",
        data={
            "full_name": "Alice Green",
            "email": "alice@ecoquest.org",
            "phone": "555-1111",
            "city": "Vancouver",
            "college": "UBC Forestry",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Register User B
    client.post(
        "/auth/register",
        data={
            "full_name": "Bob Rivers",
            "email": "bob@ecoquest.org",
            "phone": "555-2222",
            "city": "Austin",
            "college": "Texas Ecology",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )

    # Login as User A
    client.post("/auth/login", data={"email": "alice@ecoquest.org", "password": "Password123"})
    resp_a = client.get("/dashboard/")
    html_a = resp_a.data.decode("utf-8")
    assert "Welcome back, Alice Green!" in html_a
    assert "UBC Forestry" in html_a
    assert "Vancouver" in html_a
    assert "Bob Rivers" not in html_a

    # Logout and login as User B
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "bob@ecoquest.org", "password": "Password123"})
    resp_b = client.get("/dashboard/")
    html_b = resp_b.data.decode("utf-8")
    assert "Welcome back, Bob Rivers!" in html_b
    assert "Texas Ecology" in html_b
    assert "Austin" in html_b
    assert "Alice Green" not in html_b


def test_dashboard_css_responsiveness():
    """Verify that dashboard.css defines responsive breakpoints."""
    css_path = os.path.join(BASE_DIR, "static", "css", "dashboard.css")
    assert os.path.isfile(css_path)
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "max-width: 1024px" in css
    assert "max-width: 768px" in css
    assert "max-width: 480px" in css
    assert ".dash-stats-grid" in css
    assert ".impact-grid-4" in css
    assert ".rec-mission-card" in css
