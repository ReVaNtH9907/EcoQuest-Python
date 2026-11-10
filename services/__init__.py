"""
EcoQuest — Services Package.

Exposes domain business logic layers to route blueprints.
"""

from services.auth_service import (
    register_user,
    authenticate_user,
    update_user_profile,
    change_user_password,
    validate_email_format,
    validate_password_strength,
)
from services.otp_service import (
    create_email_otp,
    verify_email_otp,
    can_resend_otp,
)
from services.email_service import send_otp_email, mail
from services.phone_service import initiate_phone_verification
from services.decorators import login_required
from services.csrf import generate_csrf_token, csrf_protect
from services.dashboard_service import get_user_dashboard_data
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
    DEFAULT_BADGES,
)
from services.leaderboard_service import (
    get_leaderboard_rankings,
    get_user_leaderboard_summary,
    get_available_cities,
    get_available_colleges,
)
from services.learning_service import (
    seed_learning_curriculum,
    get_categories_with_progress,
    get_lessons,
    get_lesson_by_slug,
    evaluate_quiz_submission,
    get_user_learning_progress,
)
from services.mission_service import (
    seed_missions,
    get_missions,
    get_mission_by_slug_or_id,
    accept_mission,
    get_user_missions,
    get_user_mission_dashboard_data,
)

from services.submission_service import (
    create_submission,
    get_user_submissions,
    get_submission_by_id,
    can_user_access_evidence_file,
)
from services.evidence_storage import (
    save_evidence_media,
    get_evidence_path,
    delete_evidence_file,
)

__all__ = [
    "register_user",
    "authenticate_user",
    "update_user_profile",
    "change_user_password",
    "validate_email_format",
    "validate_password_strength",
    "create_email_otp",
    "verify_email_otp",
    "can_resend_otp",
    "send_otp_email",
    "mail",
    "initiate_phone_verification",
    "login_required",
    "generate_csrf_token",
    "csrf_protect",
    "get_user_dashboard_data",
    "calculate_user_level",
    "award_lesson_xp",
    "award_mission_xp",
    "get_user_xp_summary",
    "LEVEL_TIERS",
    "seed_badges",
    "evaluate_and_award_badges",
    "get_user_badges",
    "record_qualifying_activity",
    "get_user_streak",
    "get_leaderboard_rankings",
    "get_user_leaderboard_summary",
    "get_available_cities",
    "get_available_colleges",
    "seed_learning_curriculum",
    "get_categories_with_progress",
    "get_lessons",
    "get_lesson_by_slug",
    "evaluate_quiz_submission",
    "get_user_learning_progress",
    "seed_missions",
    "get_missions",
    "get_mission_by_slug_or_id",
    "accept_mission",
    "get_user_missions",
    "get_user_mission_dashboard_data",
    "create_submission",
    "get_user_submissions",
    "get_submission_by_id",
    "can_user_access_evidence_file",
    "save_evidence_media",
    "get_evidence_path",
    "delete_evidence_file",
]
