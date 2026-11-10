"""
Basic tests for the EcoQuest application factory and routes.

Run with:  python -m pytest tests/
"""

import pytest
from app import create_app


@pytest.fixture
def app():
    """Create an application instance configured for testing."""
    app = create_app("testing")
    yield app


@pytest.fixture
def client(app):
    """A Flask test client."""
    return app.test_client()


# --- Application factory ---

def test_app_factory_creates_app(app):
    """The factory should return a Flask app."""
    assert app is not None


def test_app_is_testing(app):
    """The testing config should set TESTING = True."""
    assert app.config["TESTING"] is True


# --- Main routes ---

def test_homepage_returns_200(client):
    """GET / should return 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_health_check(client):
    """GET /health should return JSON with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


# --- Blueprint placeholder routes ---

@pytest.mark.parametrize("path,expected_key", [
    ("/auth/login", "Auth"),
    ("/auth/register", "Auth"),
    ("/auth/logout", "Auth"),
    ("/dashboard/", "Dashboard"),
    ("/learning/", "Learning"),
    ("/missions/", "Missions"),
    ("/leaderboard/", "Leaderboard"),
    ("/profile/", "Profile"),
])
def test_blueprint_endpoints(client, path, expected_key):
    """All blueprint endpoints should return 200 (or redirect to login when protected)."""
    response = client.get(path, follow_redirects=True)
    assert response.status_code == 200
    data = response.get_json()
    if data and "message" in data:
        assert expected_key in data["message"]
    else:
        # Real HTML page rendered
        html = response.data.decode("utf-8").lower()
        assert expected_key.lower() in html or "login" in html or "ecoquest" in html


# --- Error handlers ---

def test_404_error(client):
    """A non-existent route should return 404."""
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404


def test_500_error(app):
    """Simulate a 500 error and verify the handler responds."""
    # Disable exception propagation so the 500 handler is invoked
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/force-500")
    def force_error():
        raise Exception("Intentional test error")

    with app.test_client() as client:
        response = client.get("/force-500")
        assert response.status_code == 500
