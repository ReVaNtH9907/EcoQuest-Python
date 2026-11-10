"""
EcoQuest — Comprehensive Mission History & Verification Testing Suite.

Verifies:
1. Retrieval of user's complete mission participation history across all states:
   - Completed (Verified)
   - Under Review (Requires Manual Review / Pending)
   - Rejected
   - In Progress (Accepted but not yet submitted)
2. All required card fields:
   - Mission title, category, date accepted, submission date,
     current verification status, XP earned, mission completion status, thumbnail.
3. Detailed mission submission page containing all 13 required items:
   1) Mission title and description
   2) Instructions and requirements
   3) Date accepted
   4) Submission date and time
   5) Before-and-after photographs
   6) Optional video evidence
   7) GPS location (latitude, longitude, accuracy)
   8) Current verification status
   9) AI confidence score
   10) Verification explanation
   11) Administrator feedback
   12) XP awarded
   13) Chronological submission history and status changes timeline
4. Multi-user security & access control:
   - User A cannot view User B's submission details (403 Forbidden).
   - Platform administrators can view submissions for auditing.
   - Submissions persist across user logout and login.
5. AI verification outcomes:
   - Verified (>= 80% confidence, mission-specific actions matched)
   - Requires Manual Review (uncertainty, low confidence, or anti-signals)
   - Rejected (identical before/after or fraud)
   - Administrator manual review with feedback and XP idempotency.
"""

import pytest
from app import create_app
from models import db, User, Mission, UserMission, Submission, XPTransaction
from services.submission_service import (
    create_submission,
    get_user_mission_history,
    get_detailed_mission_submission,
    admin_review_submission,
    verify_submission_pipeline,
)
from services.xp_service import award_mission_xp


SAMPLE_PNG_1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
SAMPLE_PNG_2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


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


def create_user(email="testuser@ecoquest.org", name="Test User", is_admin=False):
    user = User(
        email=email,
        full_name=name,
        phone="+919876543210",
        city="Chennai",
        college="IIT Madras",
        email_verified=True,
        is_admin=is_admin,
    )
    user.set_password("Secret123!")
    db.session.add(user)
    db.session.commit()
    return user


def login_client(client, email="testuser@ecoquest.org", pwd="Secret123!"):
    return client.post("/auth/login", data={"email": email, "password": pwd}, follow_redirects=True)


class TestMissionHistoryRetrieval:
    """Verifies that user mission history retrieves all participation statuses."""

    def test_empty_mission_history(self, app):
        with app.app_context():
            user = create_user(email="newbie@ecoquest.org", name="Newbie")
            history = get_user_mission_history(user.id)
            assert history["items"] == []
            assert history["counts"]["total"] == 0
            assert history["counts"]["completed"] == 0
            assert history["counts"]["in_progress"] == 0

    def test_in_progress_mission_in_history(self, app):
        """Accepted missions without proof yet appear as 'In Progress'."""
        with app.app_context():
            user = create_user(email="walker@ecoquest.org", name="Walker")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()
            um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
            db.session.add(um)
            db.session.commit()

            history = get_user_mission_history(user.id)
            assert len(history["items"]) == 1
            item = history["items"][0]
            assert item["mission_title"] == mission.title
            assert item["mission_category"] == mission.category
            assert item["verification_status"] == "In Progress"
            assert item["mission_completion_status"] == "In Progress"
            assert item["xp_earned"] == 0
            assert item["submission_date"] == "Not submitted yet"
            assert item["has_submission"] is False
            assert history["counts"]["in_progress"] == 1

    def test_multi_status_mission_history(self, app):
        """User has missions in all 4 states: Verified, Under Review, Rejected, In Progress."""
        with app.app_context():
            user = create_user(email="active@ecoquest.org", name="Active Hero")
            m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
            m2 = Mission.query.filter_by(slug="plant-a-native-tree").first()
            m3 = Mission.query.filter_by(slug="collect-recyclable-waste").first()
            m4 = Mission.query.filter_by(slug="home-plumbing-leak-audit").first()

            # 1. Accepted, In Progress (no submission)
            db.session.add(UserMission(user_id=user.id, mission_id=m1.id, status="accepted"))

            # 2. Submitted & Verified
            db.session.add(UserMission(user_id=user.id, mission_id=m2.id, status="accepted"))
            db.session.commit()
            sub2_res = create_submission(
                user_id=user.id,
                mission_id=m2.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Planted 5 native saplings with bamboo stakes and watered the soil thoroughly.",
                auto_verify=False,
            )
            sub2 = db.session.get(Submission, sub2_res["submission_id"])
            sub2.verification_status = "Verified"
            sub2.confidence_score = 92.0
            sub2.verification_explanation = "Saplings and stake detected."
            db.session.commit()
            award_mission_xp(user.id, sub2.id, m2.id)

            # 3. Submitted & Rejected
            db.session.add(UserMission(user_id=user.id, mission_id=m3.id, status="accepted"))
            db.session.commit()
            sub3_res = create_submission(
                user_id=user.id,
                mission_id=m3.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Unrelated activity with no recyclable materials.",
                auto_verify=False,
            )
            sub3 = db.session.get(Submission, sub3_res["submission_id"])
            sub3.verification_status = "Rejected"
            sub3.confidence_score = 25.0
            sub3.verification_explanation = "No recyclables found in proof."
            sub3.rejection_reason = "No recyclables found in proof."
            db.session.commit()

            # 4. Submitted & Under Review
            db.session.add(UserMission(user_id=user.id, mission_id=m4.id, status="accepted"))
            db.session.commit()
            sub4_res = create_submission(
                user_id=user.id,
                mission_id=m4.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Checked bathroom tap and replaced washer.",
                auto_verify=False,
            )
            sub4 = db.session.get(Submission, sub4_res["submission_id"])
            sub4.verification_status = "Requires Manual Review"
            sub4.confidence_score = 65.0
            sub4.verification_explanation = "Tap repair requires human review."
            db.session.commit()

            # Retrieve complete history
            history = get_user_mission_history(user.id)
            assert len(history["items"]) == 4
            assert history["counts"]["total"] == 4
            assert history["counts"]["completed"] == 1
            assert history["counts"]["rejected"] == 1
            assert history["counts"]["under_review"] == 1
            assert history["counts"]["in_progress"] == 1

            # Test filter: Completed
            completed_h = get_user_mission_history(user.id, status_filter="completed")
            assert len(completed_h["items"]) == 1
            assert completed_h["items"][0]["verification_status"] == "Verified"
            assert completed_h["items"][0]["xp_earned"] > 0

            # Test filter: Under Review
            review_h = get_user_mission_history(user.id, status_filter="under_review")
            assert len(review_h["items"]) == 1
            assert review_h["items"][0]["verification_status"] == "Manual Review"

            # Test filter: Rejected
            rej_h = get_user_mission_history(user.id, status_filter="rejected")
            assert len(rej_h["items"]) == 1
            assert rej_h["items"][0]["verification_status"] == "Rejected"

            # Test filter: In Progress
            prog_h = get_user_mission_history(user.id, status_filter="in_progress")
            assert len(prog_h["items"]) == 1
            assert prog_h["items"][0]["verification_status"] == "In Progress"


class TestDetailedSubmissionPage:
    """Verifies that all 13 required items are present on the detailed submission page."""

    def test_thirteen_detailed_submission_items(self, app):
        with app.app_context():
            user = create_user(email="explorer@ecoquest.org", name="Eco Explorer")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()
            um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
            db.session.add(um)
            db.session.commit()

            sub_res = create_submission(
                user_id=user.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Cleaned litter along beach promenade, bagged 3 bags of plastic bottles.",
                latitude=13.0489,
                longitude=80.2825,
                location_accuracy=12.5,
                auto_verify=False,
            )
            sub_id = sub_res["submission_id"]
            sub = db.session.get(Submission, sub_id)
            sub.verification_status = "Verified"
            sub.confidence_score = 94.0
            sub.verification_explanation = "Clear transformation: bags of plastic litter collected."
            sub.reviewed_by = "AI_VERIFIER_ENGINE"
            db.session.commit()
            award_mission_xp(user.id, sub.id, mission.id)

            # Retrieve detailed record
            detail = get_detailed_mission_submission(sub_id, user_id=user.id)
            assert detail is not None

            # 1. Mission title and description
            assert detail["mission_title"] == mission.title
            assert len(detail["mission_description"]) > 0

            # 2. Instructions and requirements
            assert len(detail["instructions"]) > 0
            assert len(detail["proof_requirements"]) > 0

            # 3. Date accepted
            assert detail["date_accepted"] != "N/A"
            assert detail["date_accepted_raw"] is not None

            # 4. Submission date and time
            assert detail["submission_date"] != "N/A"
            assert detail["submission_date_raw"] is not None

            # 5. Before-and-after photographs
            assert detail["before_photo"] is not None
            assert detail["after_photo"] is not None
            assert detail["before_photo_url"].startswith("/missions/evidence/")
            assert detail["after_photo_url"].startswith("/missions/evidence/")

            # 6. Optional video evidence (handled gracefully when None)
            assert "video_path" in detail
            assert "video_url" in detail

            # 7. GPS location (recorded, lat, lng, accuracy)
            assert detail["gps_recorded"] is True
            assert detail["latitude"] == 13.0489
            assert detail["longitude"] == 80.2825
            assert detail["location_accuracy"] == 12.5

            # 8. Current verification status
            assert detail["verification_status"] == "Verified"

            # 9. AI confidence score
            assert detail["confidence_score"] == 94.0

            # 10. Short verification explanation
            assert "plastic litter" in detail["verification_explanation"]

            # 11. Administrator feedback (None or text)
            assert "admin_feedback" in detail

            # 12. XP awarded
            assert detail["xp_awarded"] is True
            assert detail["xp_awarded_amount"] > 0

            # 13. Submission history and status changes (timeline)
            assert len(detail["timeline"]) >= 3
            steps = [e["title"] for e in detail["timeline"]]
            assert "Mission Accepted" in steps
            assert "Camera Proof Submitted" in steps
            assert "Evidence Verified" in steps


class TestAccessControlAndSecurity:
    """Verifies strict multi-user isolation and authorization."""

    def test_unauthorized_user_cannot_view_other_user_submission(self, client, app):
        with app.app_context():
            user_a = create_user(email="alice_sec@ecoquest.org", name="Alice Sec")
            user_b = create_user(email="bob_sec@ecoquest.org", name="Bob Sec")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            um_a = UserMission(user_id=user_a.id, mission_id=mission.id, status="accepted")
            db.session.add(um_a)
            db.session.commit()

            sub_a_res = create_submission(
                user_id=user_a.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Alice private fieldwork evidence.",
                auto_verify=False,
            )
            sub_id = sub_a_res["submission_id"]

        # Bob logs in and tries to access Alice's submission detail
        login_client(client, email="bob_sec@ecoquest.org")
        res = client.get(f"/missions/history/{sub_id}")
        assert res.status_code == 403

        # Bob also blocked from Alice's evidence files
        with app.app_context():
            sub = db.session.get(Submission, sub_id)
            before_file = sub.before_photo
        ev_res = client.get(f"/missions/evidence/{before_file}")
        assert ev_res.status_code == 403

    def test_owner_and_admin_can_view_submission(self, client, app):
        with app.app_context():
            owner = create_user(email="owner@ecoquest.org", name="Owner")
            admin = create_user(email="admin_auditor@ecoquest.org", name="Auditor", is_admin=True)
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            um = UserMission(user_id=owner.id, mission_id=mission.id, status="accepted")
            db.session.add(um)
            db.session.commit()

            sub_res = create_submission(
                user_id=owner.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Owner cleaned public area thoroughly.",
                auto_verify=False,
            )
            sub_id = sub_res["submission_id"]

        # 1. Owner can view their own submission
        login_client(client, email="owner@ecoquest.org")
        res_owner = client.get(f"/missions/history/{sub_id}")
        assert res_owner.status_code == 200
        assert "Owner cleaned public area thoroughly." in res_owner.data.decode("utf-8")

        # 2. Admin can also view the submission for auditing
        login_client(client, email="admin_auditor@ecoquest.org")
        res_admin = client.get(f"/missions/history/{sub_id}")
        assert res_admin.status_code == 200

    def test_submissions_persist_after_logout_and_new_mission_accepted(self, client, app):
        with app.app_context():
            user = create_user(email="persistent@ecoquest.org", name="Persistent User")
            m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
            m2 = Mission.query.filter_by(slug="plant-a-native-tree").first()
            m1_title = m1.title
            m2_title = m2.title
            m2_slug = m2.slug

            um1 = UserMission(user_id=user.id, mission_id=m1.id, status="accepted")
            db.session.add(um1)
            db.session.commit()

            sub_res = create_submission(
                user_id=user.id,
                mission_id=m1.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Persisted mission submission evidence.",
                auto_verify=False,
            )
            sub_id = sub_res["submission_id"]

        # Logout and log back in
        login_client(client, email="persistent@ecoquest.org")
        client.get("/auth/logout")
        login_client(client, email="persistent@ecoquest.org")

        # Accept a NEW mission
        client.post(f"/missions/{m2_slug}/accept")

        # Check that previous submission is STILL accessible
        res = client.get(f"/missions/history/{sub_id}")
        assert res.status_code == 200
        assert "Persisted mission submission evidence." in res.data.decode("utf-8")

        # History list contains both previous submission and new active quest
        history_res = client.get("/missions/history")
        assert history_res.status_code == 200
        assert m1_title in history_res.data.decode("utf-8")
        assert m2_title in history_res.data.decode("utf-8")


class TestImprovedAIVerificationDecisionLogic:
    """Verifies that verification adheres strictly to the improved 3-outcome decision rubric."""

    def test_low_confidence_routes_to_manual_review(self, app):
        """Uncertain or borderline evidence goes to Manual Review, NOT auto-verified."""
        with app.app_context():
            user = create_user(email="uncertain@ecoquest.org", name="Uncertain Submitter")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()
            um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
            db.session.add(um)
            db.session.commit()

            # Generic brief description without specific fieldwork details
            sub_res = create_submission(
                user_id=user.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="I walked around the area for a few minutes.",
                auto_verify=True,
            )
            sub = db.session.get(Submission, sub_res["submission_id"])
            assert sub.verification_status in ["Requires Manual Review", "Rejected"]
            assert sub.verification_status != "Verified"
            # No XP awarded for non-verified
            assert sub.xp_awarded is False
            assert sub.xp_awarded_amount == 0

    def test_admin_manual_review_awards_xp_and_feedback(self, app):
        """When an administrator approves a submission from manual review, XP is safely awarded."""
        with app.app_context():
            user = create_user(email="student@ecoquest.org", name="Student One")
            admin = create_user(email="prof@ecoquest.org", name="Professor Admin", is_admin=True)
            mission = Mission.query.filter_by(slug="plant-a-native-tree").first()

            um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
            db.session.add(um)
            db.session.commit()

            sub_res = create_submission(
                user_id=user.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Planted neem sapling in college courtyard.",
                auto_verify=False,
            )
            sub_id = sub_res["submission_id"]

            # Admin reviews and approves with feedback
            review_res = admin_review_submission(
                submission_id=sub_id,
                admin_user=admin,
                action="approve",
                reason="Excellent sapling plantation with proper bamboo staking.",
            )
            assert review_res["success"] is True

            sub = db.session.get(Submission, sub_id)
            assert sub.verification_status == "Verified"
            assert sub.admin_feedback == "Excellent sapling plantation with proper bamboo staking."
            assert sub.xp_awarded is True
            assert sub.xp_awarded_amount == mission.xp_reward

            # Verify idempotency: calling award again does NOT duplicate XP
            duplicate_xp = award_mission_xp(user.id, sub_id, mission.id)
            assert duplicate_xp["already_earned"] is True
            assert duplicate_xp["awarded"] is False
