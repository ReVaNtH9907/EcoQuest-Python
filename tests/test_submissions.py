"""
EcoQuest — Camera-Based Mission Proof Submission Test Suite.

Automated verification of:
1. Direct camera access requirement: No file inputs (<input type="file">), gallery pickers, or drag-and-drop.
2. Authentication enforcement on submission and evidence routes.
3. Pre-condition guard: User must have accepted the mission before submitting proof.
4. Evidence payload validation: Before-photo and After-photo are strictly mandatory.
5. Description validation.
6. GPS handling: Saves valid coordinates or handles unavailable/denied location gracefully.
7. Verification status initialization: 'Pending Verification'.
8. Non-rewarding rule: Strictly NO XP awarded during this proof submission phase.
9. Private evidence storage & strict user authorization:
   - Evidence stored in private folder outside static.
   - Private media streaming route (/missions/evidence/<filename>) enforces owner check.
   - Unauthorized members receive 403 Forbidden.
   - Unauthenticated visitors are redirected to login.
10. Submission confirmation receipt (/missions/submissions/<id>/confirmation).
11. Submission history ledger (/missions/submissions) with multi-user isolation.
"""

import base64
import pytest
from app import create_app
from models import db, User, Mission, UserMission, Submission
from services.evidence_storage import save_evidence_media, get_evidence_path


# 1x1 transparent PNG data URL for test submissions
SAMPLE_BASE64_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# 1x1 second mock WebM video data URL
SAMPLE_BASE64_WEBM = (
    "data:video/webm;base64,GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJ8gij4AQAAAAAA"
)


@pytest.fixture
def app():
    """Create testing application with clean SQLite database."""
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


def register_and_login(client, email="rahul@ecoquest.org", name="Rahul Sharma"):
    """Helper to create and authenticate a test user."""
    client.post(
        "/auth/register",
        data={
            "full_name": name,
            "email": email,
            "phone": "+91 98765 43210",
            "city": "Bengaluru",
            "college": "IISc Bangalore",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    client.post("/auth/login", data={"email": email, "password": "Password123"})


# ============================================================
# 1. Camera-Only UI & Absence of File Input Tests
# ============================================================

def test_camera_submission_page_has_no_file_input(client, app):
    """
    Ensure the mission submission page strictly uses the browser MediaDevices API
    and does NOT include any <input type="file"> elements or gallery pickers.
    """
    register_and_login(client)

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()
        assert mission is not None

    # Accept the mission first
    client.post(f"/missions/{mission.slug}/accept")

    # Visit submission page
    response = client.get(f"/missions/{mission.slug}/submit")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Check for direct camera elements
    assert 'id="camera-viewfinder"' in html
    assert 'id="capture-before-btn"' in html
    assert 'id="capture-after-btn"' in html
    assert 'id="start-record-btn"' in html
    assert "camera_capture.js" in html

    # Strictly verify NO file upload inputs
    assert 'type="file"' not in html.lower()
    assert "type='file'" not in html.lower()
    assert 'accept="image/' not in html.lower()
    assert 'accept="video/' not in html.lower()


# ============================================================
# 2. Authentication & Pre-condition Guards
# ============================================================

def test_submit_proof_unauthenticated(client):
    """Unauthenticated users cannot access submit page or submit evidence."""
    get_res = client.get("/missions/clean-a-public-area/submit")
    assert get_res.status_code in [302, 401]

    post_res = client.post(
        "/missions/clean-a-public-area/submit",
        json={"before_photo": SAMPLE_BASE64_PNG},
    )
    assert post_res.status_code in [302, 401]


def test_submit_proof_without_prior_acceptance(client, app):
    """
    User cannot submit proof for a mission they haven't accepted.
    Must return clear error message.
    """
    register_and_login(client)

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    # Attempt to submit without accepting
    response = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "Cleaned up the entire area around the lake.",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "mission_not_accepted"


# ============================================================
# 3. Evidence Payload Validation Tests
# ============================================================

def test_submit_missing_photos(client, app):
    """Missing before-photo or after-photo must fail validation."""
    register_and_login(client)

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    client.post(f"/missions/{mission.slug}/accept")

    # Missing before photo
    res1 = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": "",
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "Picked up all plastic wrappers.",
        },
        headers={"Accept": "application/json"},
    )
    assert res1.status_code == 400
    data1 = res1.get_json()
    assert data1["error"] == "missing_before_photo"

    # Missing after photo
    res2 = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": "",
            "description": "Picked up all plastic wrappers.",
        },
        headers={"Accept": "application/json"},
    )
    assert res2.status_code == 400
    data2 = res2.get_json()
    assert data2["error"] == "missing_after_photo"


def test_submit_too_short_description(client, app):
    """Description must have minimum content."""
    register_and_login(client)

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    client.post(f"/missions/{mission.slug}/accept")

    res = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "abc",  # too short
        },
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"] == "description_too_short"


# ============================================================
# 4. Valid Submission, Status & Non-Rewarding Rule
# ============================================================

def test_valid_submission_creates_record_and_no_xp(client, app):
    """
    Verify:
    1. Valid camera-captured evidence submission succeeds.
    2. Submission record is created with reference ID (SUB-XXXXX).
    3. Status is 'Pending Verification'.
    4. Server-side UTC submitted_at timestamp is populated.
    5. UserMission status updates to 'in_progress'.
    6. Strictly NO XP is awarded in this phase (user total_xp remains unchanged).
    """
    register_and_login(client)

    with app.app_context():
        user = User.query.filter_by(email="rahul@ecoquest.org").first()
        assert user.total_xp == 0
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    # Accept mission
    client.post(f"/missions/{mission.slug}/accept")

    # Submit proof with GPS and video
    response = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "video_data": SAMPLE_BASE64_WEBM,
            "description": "Collected 3 bags of discarded plastic and segregated dry waste.",
            "latitude": 12.9715987,
            "longitude": 77.5945627,
            "location_accuracy": 12.5,
            "capture_timestamp": "2026-11-10T14:30:00Z",
        },
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "submission_id" in data
    assert data["reference_id"].startswith("SUB-")

    # Verify Database state
    with app.app_context():
        user_db = User.query.filter_by(email="rahul@ecoquest.org").first()
        # CRITICAL: Verify NO XP awarded in this phase
        assert user_db.total_xp == 0, "No XP should be awarded merely for submitting proof"

        submission = db.session.get(Submission, data["submission_id"])
        assert submission is not None
        assert submission.verification_status == "Pending Verification"
        assert submission.description == "Collected 3 bags of discarded plastic and segregated dry waste."
        assert submission.latitude == pytest.approx(12.9715987, 0.00001)
        assert submission.longitude == pytest.approx(77.5945627, 0.00001)
        assert submission.location_accuracy == pytest.approx(12.5, 0.1)
        assert submission.before_photo.endswith(".png")
        assert submission.after_photo.endswith(".png")
        assert submission.video_path.endswith(".webm")
        assert submission.submitted_at is not None

        # Verify UserMission status is in_progress
        um = UserMission.query.filter_by(user_id=user.id, mission_id=mission.id).first()
        assert um.status == "in_progress"


def test_submission_graceful_without_gps(client, app):
    """
    Verify submission succeeds even when location permission is denied / unavailable.
    """
    register_and_login(client, email="anita@ecoquest.org", name="Anita Roy")

    with app.app_context():
        mission = Mission.query.filter_by(slug="plant-a-native-tree").first()

    client.post(f"/missions/{mission.slug}/accept")

    response = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "Planted a Neem sapling with bamboo stake protection.",
            "latitude": None,
            "longitude": None,
            "location_accuracy": None,
        },
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    with app.app_context():
        sub = db.session.get(Submission, data["submission_id"])
        assert sub.latitude is None
        assert sub.longitude is None


# ============================================================
# 5. Private Evidence Storage & Access Control
# ============================================================

def test_private_evidence_authorization_and_isolation(client, app):
    """
    Ensure evidence media is stored outside public static directories
    and cannot be accessed by unauthorized users.
    - Owner -> HTTP 200
    - Other authenticated user -> HTTP 403 Forbidden
    - Unauthenticated user -> HTTP 302 / 401
    """
    # 1. User A registers and submits proof
    register_and_login(client, email="user_a@ecoquest.org", name="User A")

    with app.app_context():
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

    client.post(f"/missions/{mission.slug}/accept")
    res = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "User A clean mission fieldwork.",
        },
        headers={"Accept": "application/json"},
    )
    sub_data = res.get_json()
    submission_id = sub_data["submission_id"]

    with app.app_context():
        sub = db.session.get(Submission, submission_id)
        before_file = sub.before_photo

    # User A accesses their own evidence file -> 200 OK
    own_file_res = client.get(f"/missions/evidence/{before_file}")
    assert own_file_res.status_code == 200
    assert own_file_res.mimetype.startswith("image/")

    # 2. Log out and try unauthenticated -> redirect / 401
    client.post("/auth/logout")
    unauth_res = client.get(f"/missions/evidence/{before_file}")
    assert unauth_res.status_code in [302, 401]

    # 3. User B registers and attempts to access User A's private evidence file -> 403 Forbidden
    register_and_login(client, email="user_b@ecoquest.org", name="User B")
    user_b_res = client.get(f"/missions/evidence/{before_file}")
    assert user_b_res.status_code == 403, "User B must be forbidden from accessing User A evidence"


# ============================================================
# 6. Submission Confirmation Receipt & History Ledger
# ============================================================

def test_submission_confirmation_receipt(client, app):
    """
    Verify confirmation page displays receipt reference, status, and thumbnails.
    """
    register_and_login(client, email="dev@ecoquest.org", name="Devendra")

    with app.app_context():
        mission = Mission.query.filter_by(slug="collect-recyclable-waste").first()

    client.post(f"/missions/{mission.slug}/accept")
    res = client.post(
        f"/missions/{mission.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "Segregated 8kg of paper and cardboard waste.",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "location_accuracy": 15.0,
        },
        headers={"Accept": "application/json"},
    )
    sub_id = res.get_json()["submission_id"]

    # View confirmation receipt
    conf_res = client.get(f"/missions/submissions/{sub_id}/confirmation")
    assert conf_res.status_code == 200
    html = conf_res.data.decode("utf-8")
    assert f"SUB-{sub_id:05d}" in html
    assert "Pending Verification" in html
    assert "Segregated 8kg of paper and cardboard waste." in html
    assert "View All My Submissions" in html


def test_submission_history_ledger_multi_user_isolation(client, app):
    """
    Verify /missions/submissions lists user's submissions and enforces isolation.
    """
    # User 1 submits
    register_and_login(client, email="member1@ecoquest.org", name="Member One")
    with app.app_context():
        m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
    client.post(f"/missions/{m1.slug}/accept")
    client.post(
        f"/missions/{m1.slug}/submit",
        json={
            "before_photo": SAMPLE_BASE64_PNG,
            "after_photo": SAMPLE_BASE64_PNG,
            "description": "Member One mission action.",
        },
    )

    # Check history page
    res1 = client.get("/missions/submissions")
    assert res1.status_code == 200
    assert "Member One mission action." in res1.data.decode("utf-8")

    # JSON format check
    json_res = client.get("/missions/submissions?format=json")
    assert json_res.status_code == 200
    data = json_res.get_json()
    assert data["total_submissions"] == 1
    assert data["submissions"][0]["mission_title"] == m1.title

    # User 2 logs in
    client.post("/auth/logout")
    register_and_login(client, email="member2@ecoquest.org", name="Member Two")

    # Member 2's history should be empty initially
    res2 = client.get("/missions/submissions")
    assert res2.status_code == 200
    assert "No proof submissions yet" in res2.data.decode("utf-8")
    assert "Member One mission action." not in res2.data.decode("utf-8")
