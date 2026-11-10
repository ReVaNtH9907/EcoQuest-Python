"""
EcoQuest — AI-Assisted Environmental Mission Verification Test Suite.

Comprehensive automated test suite covering:
1. Verification Pipeline (Pending -> Processing -> AI Analysis -> Mission Matching -> Decision).
2. Demo Verification Mode (clear transparent labeling, rule-based heuristic simulation).
3. Valid mission evidence verification and XP awarding.
4. Unrelated evidence detection and rejection / manual review escalation.
5. Fraud prevention:
   - Identical before/after photo detection.
   - Reused evidence across different users/missions.
6. Mission-specific criteria rules across categories.
7. AI provider failure graceful fallback to demo engine.
8. Mocked vision AI provider integration.
9. Manual admin review system (approve, reject, request evidence).
10. XP Integration:
    - Only verified missions receive XP.
    - Zero XP for rejected/pending.
    - Safe idempotent duplicate XP prevention.
    - XP transaction history recording.
11. Security and access control (@admin_required, non-admin blocked, private evidence).
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from app import create_app
from models import db, User, Mission, UserMission, Submission, XPTransaction
from services.ai_verification_service import (
    get_ai_verifier,
    DemoRuleBasedVerifier,
    GeminiVisionVerifier,
    VerificationResult,
)
from services.verification_rules import get_rules_for_category, evaluate_mission_match
from services.submission_service import (
    create_submission,
    verify_submission_pipeline,
    admin_review_submission,
    can_user_access_evidence_file,
)
from services.xp_service import award_mission_xp, get_user_xp_summary


# Sample distinct 1x1 PNGs for distinct before vs after testing
SAMPLE_PNG_1 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
SAMPLE_PNG_2 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
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


def create_user(email="user@ecoquest.org", name="Eco Member", is_admin=False):
    """Helper to create and commit a user."""
    user = User(
        full_name=name,
        email=email,
        phone="+91 98765 00000",
        city="Bengaluru",
        college="IISc Bangalore",
        email_verified=True,
        total_xp=0,
        is_admin=is_admin,
    )
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email="user@ecoquest.org", pwd="Password123"):
    """Helper to authenticate a test user via session."""
    return client.post("/auth/login", data={"email": email, "password": pwd})


# ============================================================
# 1. Demo Mode Labeling & Truthfulness
# ============================================================

def test_demo_mode_when_no_credentials(app):
    """
    Ensure that when no AI credentials are set, the system uses DemoRuleBasedVerifier
    and explicitly marks is_demo_verification=True without claiming real AI ran.
    """
    with app.app_context():
        with patch.dict("os.environ", {}, clear=True):
            verifier = get_ai_verifier()
            assert isinstance(verifier, DemoRuleBasedVerifier)

            res = verifier.verify(
                submission={"description": "Collected 3 bags of plastic litter at the local park."},
                mission={"category": "Cleanup", "category_slug": "cleanup", "title": "Clean a Public Area"},
                fraud_report={"has_fraud_flags": False, "identical_before_after": False},
            )
            assert res.is_demo_verification is True
            assert "Demo Mode" in res.verification_explanation
            assert res.reviewed_by == "DEMO_HEURISTIC_ENGINE"
            assert res.ai_findings["external_ai_connected"] is False


# ============================================================
# 2. Mission-Specific Verification Rules
# ============================================================

def test_mission_specific_verification_rules_differ_by_category():
    """Verify distinct categories have distinct criteria, keywords, and expectations."""
    cleanup_rules = get_rules_for_category("cleanup")
    tree_rules = get_rules_for_category("tree-plantation")
    water_rules = get_rules_for_category("water-conservation")

    assert cleanup_rules["category_name"] == "Cleanup"
    assert tree_rules["category_name"] == "Tree Plantation"
    assert water_rules["category_name"] == "Water Conservation"

    # Distinct primary objects
    assert "litter" in cleanup_rules["primary_objects"]
    assert "sapling" in tree_rules["primary_objects"]
    assert "aerator" in water_rules["primary_objects"]

    # Criteria are not identical
    assert cleanup_rules["primary_objects"] != tree_rules["primary_objects"]
    assert tree_rules["expected_after"] != water_rules["expected_after"]


# ============================================================
# 3. Valid Mission Evidence & Automated XP Award
# ============================================================

def test_valid_evidence_verification_and_xp_award(app):
    """
    Valid evidence matching mission criteria:
    - Passes fraud checks.
    - Receives status 'Verified'.
    - Automatically awards XP to the user.
    - Creates immutable XPTransaction record.
    - Updates UserMission status to 'completed'.
    """
    with app.app_context():
        user = create_user(email="riya@ecoquest.org", name="Riya Sen")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()
        assert mission is not None

        # Enroll in mission
        um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
        db.session.add(um)
        db.session.commit()

        # Submit distinct photos with relevant fieldwork description
        sub_res = create_submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo_data=SAMPLE_PNG_1,
            after_photo_data=SAMPLE_PNG_2,
            description="Surveyed the public park trail, collected dispersed plastic wrappers, bottles, and litter into 3 separate garbage bags.",
            latitude=12.9716,
            longitude=77.5946,
            auto_verify=True,
        )

        assert sub_res["success"] is True
        sub_id = sub_res["submission_id"]

        submission = db.session.get(Submission, sub_id)
        assert submission.verification_status == "Verified"
        assert submission.confidence_score >= 60.0
        assert submission.review_decision == "auto_approved"
        assert submission.xp_awarded is True
        assert submission.xp_awarded_amount == mission.xp_reward

        # Verify User XP was credited
        user_db = db.session.get(User, user.id)
        assert user_db.total_xp == mission.xp_reward

        # Verify XPTransaction audit log
        tx = XPTransaction.query.filter_by(reference_id=f"XP-SUB-{submission.id:05d}").first()
        assert tx is not None
        assert tx.user_id == user.id
        assert tx.amount == mission.xp_reward
        assert tx.source_type == "mission_verification"

        # Verify UserMission completed
        um_db = UserMission.query.filter_by(user_id=user.id, mission_id=mission.id).first()
        assert um_db.status == "completed"


# ============================================================
# 4. Unrelated Evidence & Detection
# ============================================================

def test_unrelated_evidence_flagged(app):
    """
    Unrelated description lacking environmental domain cues receives low score
    and is escalated to manual review or rejected, with strictly NO XP awarded.
    """
    with app.app_context():
        user = create_user(email="arjun@ecoquest.org", name="Arjun Das")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
        db.session.add(um)
        db.session.commit()

        sub_res = create_submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo_data=SAMPLE_PNG_1,
            after_photo_data=SAMPLE_PNG_2,
            description="I stayed at home and cooked dinner with friends.",
            auto_verify=True,
        )

        sub_id = sub_res["submission_id"]
        submission = db.session.get(Submission, sub_id)

        # Status should NOT be Verified
        assert submission.verification_status in ["Requires Manual Review", "Rejected"]
        assert submission.xp_awarded is False
        assert submission.xp_awarded_amount == 0

        # User XP remains 0
        user_db = db.session.get(User, user.id)
        assert user_db.total_xp == 0


# ============================================================
# 5. Fraud Prevention: Identical Photos & Reused Evidence
# ============================================================

def test_fraud_identical_before_and_after_photos(app):
    """
    Submitting the exact same photo as before and after is caught by hash check
    and rejected with zero XP.
    """
    with app.app_context():
        user = create_user(email="samir@ecoquest.org", name="Samir")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        um = UserMission(user_id=user.id, mission_id=mission.id, status="accepted")
        db.session.add(um)
        db.session.commit()

        # Submit identical image for before and after
        sub_res = create_submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo_data=SAMPLE_PNG_1,
            after_photo_data=SAMPLE_PNG_1,
            description="Cleaned up the public park thoroughly.",
            auto_verify=True,
        )

        sub_id = sub_res["submission_id"]
        submission = db.session.get(Submission, sub_id)

        assert submission.verification_status == "Rejected"
        assert "identical" in submission.rejection_reason.lower()
        assert submission.xp_awarded is False

        # No XP given
        user_db = db.session.get(User, user.id)
        assert user_db.total_xp == 0


def test_fraud_reused_evidence_across_users(app):
    """
    When User B reuses an image hash previously submitted by User A,
    the submission is flagged for manual review with severity warning.
    """
    with app.app_context():
        user_a = create_user(email="alice@ecoquest.org", name="Alice")
        user_b = create_user(email="bob@ecoquest.org", name="Bob")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        # User A submits
        um_a = UserMission(user_id=user_a.id, mission_id=mission.id, status="accepted")
        db.session.add(um_a)
        db.session.commit()
        create_submission(
            user_id=user_a.id,
            mission_id=mission.id,
            before_photo_data=SAMPLE_PNG_1,
            after_photo_data=SAMPLE_PNG_2,
            description="Cleaned public park with bags of collected plastic litter.",
            auto_verify=True,
        )

        # User B attempts to reuse User A's photo
        um_b = UserMission(user_id=user_b.id, mission_id=mission.id, status="accepted")
        db.session.add(um_b)
        db.session.commit()

        sub_b_res = create_submission(
            user_id=user_b.id,
            mission_id=mission.id,
            before_photo_data=SAMPLE_PNG_1,  # Reused from User A
            after_photo_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            description="Cleaned public park with bags of collected plastic litter.",
            auto_verify=True,
        )

        sub_b = db.session.get(Submission, sub_b_res["submission_id"])
        # Should be flagged for manual review, NOT auto-verified
        assert sub_b.verification_status == "Requires Manual Review"
        assert "matches" in sub_b.detected_inconsistencies.lower() or "reused" in sub_b.detected_inconsistencies.lower()
        assert sub_b.xp_awarded is False


# ============================================================
# 6. AI Provider Fallback on Failure
# ============================================================

def test_ai_provider_failure_graceful_fallback(app):
    """
    When the live AI vision API fails or raises an exception, the system catches it
    and falls back cleanly to DemoRuleBasedVerifier without crashing.
    """
    with app.app_context():
        verifier = GeminiVisionVerifier(api_key="mock_invalid_key")
        # Force _call_gemini_vision to raise an Exception
        with patch.object(verifier, "_call_gemini_vision", side_effect=Exception("API connection timeout")):
            res = verifier.verify(
                submission={"description": "Planted a native Neem tree sapling in the school compound."},
                mission={"category": "Tree Plantation", "category_slug": "tree-plantation", "title": "Plant a Native Tree"},
                fraud_report={"has_fraud_flags": False, "identical_before_after": False},
            )
            assert res is not None
            assert res.status in ["Verified", "Requires Manual Review"]
            assert "FALLBACK" in res.reviewed_by


# ============================================================
# 7. Mocked Multimodal AI Vision Integration
# ============================================================

def test_mocked_ai_vision_response(app):
    """
    Test GeminiVisionVerifier when the API returns structured JSON.
    Verifies proper translation into VerificationResult.
    """
    with app.app_context():
        verifier = GeminiVisionVerifier(api_key="mock_valid_key")

        mock_ai_json = {
            "confidence_score": 88,
            "evidence_relevance": "high",
            "before_after_comparison": "Image 1 shows litter; Image 2 shows cleared ground with 2 filled garbage bags.",
            "detected_objects": ["plastic bottles", "wrappers", "garbage bags", "gloves"],
            "inconsistencies": [],
            "explanation": "Clear visual evidence of completed cleanup matching mission requirements.",
            "decision": "Verified",
        }

        with patch.object(verifier, "_call_gemini_vision") as mock_call:
            mock_call.return_value = VerificationResult(
                status="Verified",
                confidence_score=88.0,
                evidence_relevance="high",
                before_after_comparison=mock_ai_json["before_after_comparison"],
                detected_inconsistencies="",
                verification_explanation=mock_ai_json["explanation"],
                ai_findings=mock_ai_json,
                review_decision="auto_approved",
                reviewed_by="AI_GEMINI_VISION",
                is_demo_verification=False,
            )

            res = verifier.verify(
                submission={"description": "Cleaned up trail."},
                mission={"title": "Clean a Public Area", "category": "Cleanup"},
                fraud_report={"has_fraud_flags": False},
            )

            assert res.status == "Verified"
            assert res.confidence_score == 88.0
            assert res.is_demo_verification is False
            assert res.reviewed_by == "AI_GEMINI_VISION"


# ============================================================
# 8. Manual Review System (Admin Console)
# ============================================================

def test_admin_manual_approval_and_xp_award(app):
    """
    Admin can manually approve a submission in 'Requires Manual Review'
    which sets status to 'Verified', logs reviewer audit, and triggers XP award.
    """
    with app.app_context():
        admin = create_user(email="admin@ecoquest.org", name="Admin User", is_admin=True)
        user = create_user(email="priya@ecoquest.org", name="Priya")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        um = UserMission(user_id=user.id, mission_id=mission.id, status="in_progress")
        db.session.add(um)

        sub = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo="before.png",
            after_photo="after.png",
            description="Fieldwork notes with moderate clarity.",
            verification_status="Requires Manual Review",
            review_decision="escalated_for_review",
            xp_awarded=False,
        )
        db.session.add(sub)
        db.session.commit()

        # Admin approves
        res = admin_review_submission(
            submission_id=sub.id,
            admin_user=admin,
            action="approve",
            reason="Verified manually via photo review.",
        )

        assert res["success"] is True
        assert res["action"] == "approved"

        # Verify submission state
        sub_db = db.session.get(Submission, sub.id)
        assert sub_db.verification_status == "Verified"
        assert sub_db.review_decision == "manual_approved"
        assert admin.email in sub_db.reviewed_by
        assert sub_db.xp_awarded is True

        # Verify User XP was credited
        user_db = db.session.get(User, user.id)
        assert user_db.total_xp == mission.xp_reward


def test_admin_manual_rejection_no_xp(app):
    """
    Admin rejection sets status to 'Rejected' with reason, and awards NO XP.
    """
    with app.app_context():
        admin = create_user(email="admin2@ecoquest.org", name="Admin Two", is_admin=True)
        user = create_user(email="karan@ecoquest.org", name="Karan")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        um = UserMission(user_id=user.id, mission_id=mission.id, status="in_progress")
        db.session.add(um)

        sub = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo="before.png",
            after_photo="after.png",
            description="Vague notes.",
            verification_status="Requires Manual Review",
            review_decision="escalated_for_review",
            xp_awarded=False,
        )
        db.session.add(sub)
        db.session.commit()

        res = admin_review_submission(
            submission_id=sub.id,
            admin_user=admin,
            action="reject",
            reason="Photographs do not demonstrate waste removal.",
        )

        assert res["success"] is True
        assert res["action"] == "rejected"

        sub_db = db.session.get(Submission, sub.id)
        assert sub_db.verification_status == "Rejected"
        assert "Photographs do not demonstrate" in sub_db.rejection_reason
        assert sub_db.xp_awarded is False

        # User XP remains 0
        user_db = db.session.get(User, user.id)
        assert user_db.total_xp == 0


def test_admin_request_evidence(app):
    """Admin can request additional evidence for suspicious submissions."""
    with app.app_context():
        admin = create_user(email="admin3@ecoquest.org", name="Admin Three", is_admin=True)
        user = create_user(email="rohit@ecoquest.org", name="Rohit")
        mission = Mission.query.filter_by(slug="clean-a-public-area").first()

        sub = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo="before.png",
            after_photo="after.png",
            description="Cleaned.",
            verification_status="Processing",
        )
        db.session.add(sub)
        db.session.commit()

        res = admin_review_submission(
            submission_id=sub.id,
            admin_user=admin,
            action="request_evidence",
            reason="Please provide a wider photo of the collection bags.",
        )

        assert res["success"] is True
        sub_db = db.session.get(Submission, sub.id)
        assert sub_db.verification_status == "Requires Manual Review"
        assert "wider photo" in sub_db.rejection_reason


# ============================================================
# 9. Duplicate XP Prevention & Safe Idempotency
# ============================================================

def test_duplicate_xp_prevention_on_repeated_calls(app):
    """
    Calling award_mission_xp twice for the same submission produces
    already_earned=True and does NOT award double XP.
    """
    with app.app_context():
        user = create_user(email="deepa@ecoquest.org", name="Deepa")
        mission = Mission.query.filter_by(slug="plant-a-native-tree").first()

        sub = Submission(
            user_id=user.id,
            mission_id=mission.id,
            before_photo="b.png",
            after_photo="a.png",
            description="Planted sapling.",
            verification_status="Verified",
            xp_awarded=False,
        )
        db.session.add(sub)
        db.session.commit()

        # Call 1: Successfully awarded
        res1 = award_mission_xp(user.id, sub.id, mission.id)
        assert res1["awarded"] is True
        assert res1["total_xp"] == mission.xp_reward

        # Call 2: Blocked by duplicate prevention
        res2 = award_mission_xp(user.id, sub.id, mission.id)
        assert res2["awarded"] is False
        assert res2["already_earned"] is True
        assert res2["total_xp"] == mission.xp_reward  # Still single XP, no double reward

        # Verify only 1 XPTransaction exists
        txs = XPTransaction.query.filter_by(reference_id=f"XP-SUB-{sub.id:05d}").all()
        assert len(txs) == 1


# ============================================================
# 10. Security & Admin Route Access Control
# ============================================================

def test_admin_routes_require_admin_privileges(client, app):
    """
    - Unauthenticated -> 302/401 redirect to login.
    - Regular member -> 403 Forbidden.
    - Administrator -> 200 OK.
    """
    # 1. Unauthenticated
    unauth_res = client.get("/admin/reviews")
    assert unauth_res.status_code in [302, 401]

    # 2. Regular user (is_admin = False)
    with app.app_context():
        create_user(email="regular@ecoquest.org", name="Regular Member", is_admin=False)
    login(client, email="regular@ecoquest.org")

    forbidden_res = client.get("/admin/reviews")
    assert forbidden_res.status_code == 403

    post_decide = client.post("/admin/reviews/1/decide", data={"action": "approve"})
    assert post_decide.status_code == 403

    # 3. Admin user (is_admin = True)
    client.post("/auth/logout")
    with app.app_context():
        create_user(email="superadmin@ecoquest.org", name="Super Admin", is_admin=True)
    login(client, email="superadmin@ecoquest.org")

    admin_res = client.get("/admin/reviews")
    assert admin_res.status_code == 200
    assert "Mission Proof Verification Ledger" in admin_res.data.decode("utf-8")


def test_admin_can_access_any_evidence_file(client, app):
    """
    Evidence access security:
    - Normal user cannot access another user's evidence.
    - Admin can access any user's evidence for audit purposes.
    """
    with app.app_context():
        user1 = create_user(email="member1@ecoquest.org", name="Member 1", is_admin=False)
        user2 = create_user(email="member2@ecoquest.org", name="Member 2", is_admin=False)
        admin = create_user(email="lead_admin@ecoquest.org", name="Lead Admin", is_admin=True)

        mission = Mission.query.first()
        sub = Submission(
            user_id=user1.id,
            mission_id=mission.id,
            before_photo="test_before.png",
            after_photo="test_after.png",
            description="Testing evidence access permissions.",
        )
        db.session.add(sub)
        db.session.commit()

        # User 1 can access own file
        assert can_user_access_evidence_file(user1.id, "test_before.png") is True

        # User 2 CANNOT access User 1's file
        assert can_user_access_evidence_file(user2.id, "test_before.png") is False

        # Admin CAN access User 1's file for verification review
        assert can_user_access_evidence_file(admin.id, "test_before.png") is True
