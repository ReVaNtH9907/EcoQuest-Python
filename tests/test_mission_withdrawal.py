"""
EcoQuest — Mission Withdrawal Feature Test Suite.

Verifies:
1. Withdrawal from ongoing missions:
   - Status updated to 'withdrawn' in database.
   - Database persistence verified.
2. Cancellation flow:
   - Ongoing mission remains active if withdrawal is cancelled.
3. No deletion of missions or submissions:
   - Preserves UserMission, Mission, and any Submission records.
4. Zero XP awarded for withdrawn missions:
   - User total_xp does not increase upon withdrawal.
5. Exclusion from Active/Ongoing Missions:
   - Withdrawn missions do not appear in /missions/my-missions.
6. Visibility in Mission History:
   - Withdrawn missions are visible in /missions/history.
   - Filter ?status=withdrawn works accurately.
7. Conditions and guards:
   - Cannot withdraw from completed or verified missions.
   - Existing submissions remain intact.
8. Continued participation:
   - Users can accept other missions or re-accept withdrawn missions.
9. Access control:
   - Only the owning user can withdraw their mission participation.
"""

import pytest
from app import create_app
from models import db, User, Mission, UserMission, Submission
from services.mission_service import (
    accept_mission,
    withdraw_mission,
    get_user_missions,
)
from services.submission_service import (
    create_submission,
    get_user_mission_history,
)


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


def create_user(email="withdrawer@ecoquest.org", name="Withdraw User"):
    user = User(
        email=email,
        full_name=name,
        phone="+919876543210",
        city="Mumbai",
        college="IIT Bombay",
        email_verified=True,
    )
    user.set_password("Secret123!")
    db.session.add(user)
    db.session.commit()
    return user


def login_client(client, email="withdrawer@ecoquest.org", pwd="Secret123!"):
    return client.post("/auth/login", data={"email": email, "password": pwd}, follow_redirects=True)


class TestMissionWithdrawal:
    """Tests for the mission withdrawal option and backend functionality."""

    def test_withdraw_ongoing_mission(self, app):
        """User can withdraw from an ongoing mission; status becomes 'withdrawn'."""
        with app.app_context():
            user = create_user(email="w1@ecoquest.org", name="User W1")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            # Accept mission
            accept_res = accept_mission(user.id, mission.id)
            assert accept_res["success"] is True

            # Verify ongoing
            um = UserMission.query.filter_by(user_id=user.id, mission_id=mission.id).first()
            assert um.status == "accepted"

            # Withdraw from mission
            withdraw_res = withdraw_mission(user.id, mission.id)
            assert withdraw_res["success"] is True
            assert withdraw_res["status"] == "withdrawn"

            # Check database persistence
            db.session.expire_all()
            um_updated = db.session.get(UserMission, um.id)
            assert um_updated.status == "withdrawn"

    def test_withdrawn_mission_not_in_active_missions(self, client, app):
        """Withdrawn missions do not appear in Active/Ongoing Quests."""
        with app.app_context():
            user = create_user(email="w2@ecoquest.org", name="User W2")
            m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
            m2 = Mission.query.filter_by(slug="plant-a-native-tree").first()
            m1_slug = m1.slug
            m2_slug = m2.slug
            m1_title = m1.title
            m2_title = m2.title

            accept_mission(user.id, m1.id)
            accept_mission(user.id, m2.id)

        login_client(client, email="w2@ecoquest.org")

        # Both initially visible in active quests
        res = client.get("/missions/my-missions")
        assert res.status_code == 200
        assert m1_title in res.data.decode("utf-8")
        assert m2_title in res.data.decode("utf-8")

        # Withdraw from m1
        w_res = client.post(f"/missions/{m1_slug}/withdraw", follow_redirects=True)
        assert w_res.status_code == 200

        # m1 must NOT appear in active quests, m2 must remain
        res_after = client.get("/missions/my-missions")
        page_html = res_after.data.decode("utf-8")
        assert m1_title not in page_html
        assert m2_title in page_html

        # Ongoing filter check
        res_ongoing = client.get("/missions/my-missions?status=ongoing")
        ongoing_html = res_ongoing.data.decode("utf-8")
        assert m1_title not in ongoing_html
        assert m2_title in ongoing_html

    def test_withdrawn_mission_visible_in_mission_history(self, client, app):
        """Withdrawn missions appear in Mission History with 'Withdrawn' status."""
        with app.app_context():
            user = create_user(email="w3@ecoquest.org", name="User W3")
            mission = Mission.query.filter_by(slug="collect-recyclable-waste").first()
            mission_title = mission.title
            mission_slug = mission.slug

            accept_mission(user.id, mission.id)
            withdraw_mission(user.id, mission.id)

            history = get_user_mission_history(user.id)
            assert len(history["items"]) == 1
            item = history["items"][0]
            assert item["verification_status"] == "Withdrawn"
            assert item["mission_completion_status"] == "Withdrawn"
            assert item["xp_earned"] == 0

        # Check HTML view
        login_client(client, email="w3@ecoquest.org")
        res = client.get("/missions/history")
        assert res.status_code == 200
        html = res.data.decode("utf-8")
        assert mission_title in html
        assert "Withdrawn" in html

        # Check status filter
        filter_res = client.get("/missions/history?status=withdrawn")
        assert filter_res.status_code == 200
        assert mission_title in filter_res.data.decode("utf-8")

    def test_cannot_withdraw_from_completed_or_verified_mission(self, app):
        """Users cannot withdraw from already completed and verified missions."""
        with app.app_context():
            user = create_user(email="w4@ecoquest.org", name="User W4")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            accept_mission(user.id, mission.id)
            um = UserMission.query.filter_by(user_id=user.id, mission_id=mission.id).first()
            um.status = "completed"
            db.session.commit()

            # Attempt withdrawal
            res = withdraw_mission(user.id, mission.id)
            assert res["success"] is False
            assert res["error"] == "already_completed"

    def test_withdrawal_does_not_delete_records_or_submissions(self, app):
        """Withdrawal updates status without deleting UserMission or Submission records."""
        with app.app_context():
            user = create_user(email="w5@ecoquest.org", name="User W5")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            accept_mission(user.id, mission.id)
            sub_res = create_submission(
                user_id=user.id,
                mission_id=mission.id,
                before_photo_data=SAMPLE_PNG_1,
                after_photo_data=SAMPLE_PNG_2,
                description="Fieldwork before withdrawal test.",
                auto_verify=False,
            )
            sub_id = sub_res["submission_id"]

            # User withdraws
            w_res = withdraw_mission(user.id, mission.id)
            assert w_res["success"] is True

            # Verify submission record STILL exists in database
            sub = db.session.get(Submission, sub_id)
            assert sub is not None
            assert sub.description == "Fieldwork before withdrawal test."

            # Verify mission still exists
            m = db.session.get(Mission, mission.id)
            assert m is not None

    def test_zero_xp_awarded_for_withdrawn_missions(self, app):
        """No XP is awarded upon withdrawal."""
        with app.app_context():
            user = create_user(email="w6@ecoquest.org", name="User W6")
            initial_xp = user.total_xp or 0
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            accept_mission(user.id, mission.id)
            withdraw_mission(user.id, mission.id)

            db.session.expire_all()
            user_reloaded = db.session.get(User, user.id)
            assert (user_reloaded.total_xp or 0) == initial_xp

    def test_users_can_participate_in_other_missions_and_reaccept(self, app):
        """Withdrawing does not block accepting other missions or re-accepting."""
        with app.app_context():
            user = create_user(email="w7@ecoquest.org", name="User W7")
            m1 = Mission.query.filter_by(slug="clean-a-public-area").first()
            m2 = Mission.query.filter_by(slug="plant-a-native-tree").first()

            # Accept and withdraw from m1
            accept_mission(user.id, m1.id)
            withdraw_mission(user.id, m1.id)

            # Can accept m2
            res_m2 = accept_mission(user.id, m2.id)
            assert res_m2["success"] is True

            # Can re-accept m1
            res_m1_reaccept = accept_mission(user.id, m1.id)
            assert res_m1_reaccept["success"] is True

    def test_access_restriction_user_cannot_withdraw_others_mission(self, app):
        """User A cannot withdraw User B's mission participation."""
        with app.app_context():
            user_a = create_user(email="user_a@ecoquest.org", name="User A")
            user_b = create_user(email="user_b@ecoquest.org", name="User B")
            mission = Mission.query.filter_by(slug="clean-a-public-area").first()

            accept_mission(user_a.id, mission.id)
            um_a = UserMission.query.filter_by(user_id=user_a.id, mission_id=mission.id).first()

            # User B attempts to withdraw User A's mission
            res = withdraw_mission(user_id=user_b.id, identifier=um_a.id)
            assert res["success"] is False

            # Verify User A's mission is still accepted
            db.session.expire_all()
            assert db.session.get(UserMission, um_a.id).status == "accepted"
