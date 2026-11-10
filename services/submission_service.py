"""
EcoQuest — Mission Proof Submission & Verification Orchestration Service.

Manages the end-to-end lifecycle of camera-captured mission evidence:
1. Proof Submission:
   - Secure media intake and hashing (SHA-256).
   - GPS telemetry extraction.
   - Initial state registration ('Pending' / 'Pending Verification').
2. Evidence Validation & Fraud Prevention:
   - Duplicate image detection across submissions.
   - Comparison of before vs. after image hashes.
   - Physical storage integrity checks.
3. AI Verification Pipeline:
   - Modular connection to vision-capable AI or deterministic heuristic demo engine.
   - Domain-specific mission matching (Cleanup, Tree Plantation, Recycling, etc.).
   - Confidence scoring and structured finding compilation.
4. XP Integration:
   - Idempotent award of mission XP strictly upon verification.
   - Zero XP for rejected or pending submissions.
5. Manual Review System:
   - Administrative review queue and decision recording.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from models import db, User, Mission, UserMission, Submission, utc_now
from services.evidence_storage import (
    save_evidence_media,
    delete_evidence_file,
    get_evidence_path,
)
from services.fraud_prevention import (
    compute_image_hash,
    detect_evidence_fraud,
    validate_submission_media_integrity,
)
from services.ai_verification_service import get_ai_verifier
from services.xp_service import award_mission_xp


def create_submission(
    user_id: int,
    mission_id: int,
    before_photo_data: Union[str, bytes],
    after_photo_data: Union[str, bytes],
    description: str,
    video_data: Optional[Union[str, bytes]] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location_accuracy: Optional[float] = None,
    capture_timestamp: Optional[str] = None,
    auto_verify: bool = False,
) -> Dict[str, Any]:
    """
    Create a new mission proof submission with camera-captured media.

    Rules:
    - User must exist.
    - Mission must exist and user must have an accepted/ongoing UserMission record.
    - Before photo and After photo are strictly required.
    - Description is required (minimum 5 characters).
    - Status is initialized to 'Pending Verification'.
    - If auto_verify=True, immediately triggers the AI verification pipeline.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"success": False, "error": "user_not_found", "message": "User not found."}

    mission = db.session.get(Mission, mission_id)
    if not mission:
        return {"success": False, "error": "mission_not_found", "message": "Mission not found."}

    # Verify user has accepted the mission
    user_mission = UserMission.query.filter_by(
        user_id=user_id,
        mission_id=mission_id,
    ).filter(UserMission.status.in_(["accepted", "in_progress"])).first()

    if not user_mission:
        return {
            "success": False,
            "error": "mission_not_accepted",
            "message": "You must accept this mission before submitting verification proof.",
        }

    # Validate required fields
    if not before_photo_data:
        return {"success": False, "error": "missing_before_photo", "message": "Before-photo evidence is required."}

    if not after_photo_data:
        return {"success": False, "error": "missing_after_photo", "message": "After-photo evidence is required."}

    clean_desc = (description or "").strip()
    if len(clean_desc) < 5:
        return {
            "success": False,
            "error": "description_too_short",
            "message": "Please provide a brief description of the fieldwork actions you completed.",
        }

    saved_files = []
    try:
        # Save Before Photo
        before_filename = save_evidence_media(before_photo_data, prefix=f"before_m{mission_id}")
        saved_files.append(before_filename)

        # Save After Photo
        after_filename = save_evidence_media(after_photo_data, prefix=f"after_m{mission_id}")
        saved_files.append(after_filename)

        # Save Optional Video
        video_filename = None
        if video_data:
            video_filename = save_evidence_media(video_data, prefix=f"video_m{mission_id}", is_video=True)
            saved_files.append(video_filename)

        # Compute cryptographic image hashes for fraud tracking
        before_hash = compute_image_hash(before_filename)
        after_hash = compute_image_hash(after_filename)

        # Parse client timestamp if provided
        parsed_capture_ts = None
        if capture_timestamp:
            try:
                clean_ts = capture_timestamp.replace("Z", "+00:00")
                parsed_capture_ts = datetime.fromisoformat(clean_ts).replace(tzinfo=None)
            except Exception:
                parsed_capture_ts = None

        # Clean GPS floats
        parsed_lat = None
        parsed_lng = None
        parsed_acc = None
        if latitude is not None and latitude != "":
            try:
                parsed_lat = round(float(latitude), 7)
            except (ValueError, TypeError):
                pass
        if longitude is not None and longitude != "":
            try:
                parsed_lng = round(float(longitude), 7)
            except (ValueError, TypeError):
                pass
        if location_accuracy is not None and location_accuracy != "":
            try:
                parsed_acc = round(float(location_accuracy), 2)
            except (ValueError, TypeError):
                pass

        # Create submission record
        submission = Submission(
            user_id=user_id,
            mission_id=mission_id,
            before_photo=before_filename,
            after_photo=after_filename,
            video_path=video_filename,
            description=clean_desc,
            latitude=parsed_lat,
            longitude=parsed_lng,
            location_accuracy=parsed_acc,
            capture_timestamp=parsed_capture_ts,
            submitted_at=utc_now(),
            verification_status="Pending Verification",
            image_hash_before=before_hash,
            image_hash_after=after_hash,
            review_decision="pending_review",
            xp_awarded=False,
            xp_awarded_amount=0,
        )
        db.session.add(submission)

        # Update UserMission status to in_progress
        user_mission.status = "in_progress"

        db.session.commit()

        # If auto_verify requested, trigger the verification pipeline
        verification_output = None
        if auto_verify:
            verification_output = verify_submission_pipeline(submission.id, auto_award_xp=True)

        return {
            "success": True,
            "message": "Mission proof submitted successfully! Your evidence is now in the verification pipeline.",
            "submission_id": submission.id,
            "reference_id": submission.reference_id,
            "submission": submission.to_dict(),
            "verification": verification_output,
        }

    except Exception as e:
        db.session.rollback()
        # Rollback saved media files to prevent orphaned disk files
        for f in saved_files:
            delete_evidence_file(f)
        return {
            "success": False,
            "error": "submission_failed",
            "message": f"Failed to save mission evidence: {str(e)}",
        }


def verify_submission_pipeline(
    submission_id: int,
    auto_award_xp: bool = True,
) -> Dict[str, Any]:
    """
    Executes the complete verification pipeline for a mission submission:
    Step 1: Status -> 'Processing'
    Step 2: Evidence Validation & Fraud Prevention check
    Step 3: AI Analysis via Vision API or Heuristic Engine
    Step 4: Mission Matching against category rules
    Step 5: Verification Decision ('Verified', 'Rejected', 'Requires Manual Review')
    Step 6: XP Awarding (if Verified and not already awarded)
    """
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return {"success": False, "error": "submission_not_found", "message": "Submission not found."}

    mission = db.session.get(Mission, submission.mission_id)
    if not mission:
        return {"success": False, "error": "mission_not_found", "message": "Mission not found."}

    user = db.session.get(User, submission.user_id)
    if not user:
        return {"success": False, "error": "user_not_found", "message": "User not found."}

    # Step 1: Transition to Processing
    submission.verification_status = "Processing"
    db.session.commit()

    # Step 2: Evidence Integrity & Fraud Check
    media_check = validate_submission_media_integrity(
        before_filename=submission.before_photo,
        after_filename=submission.after_photo,
        video_filename=submission.video_path,
    )

    if not media_check["valid"]:
        submission.verification_status = "Requires Manual Review"
        submission.review_decision = "escalated_for_review"
        submission.verification_explanation = f"Storage integrity issue: {'; '.join(media_check['errors'])}"
        submission.confidence_score = 20.0
        db.session.commit()
        return {
            "success": True,
            "status": submission.verification_status,
            "decision": submission.review_decision,
            "explanation": submission.verification_explanation,
            "submission": submission.to_dict(),
        }

    # Compute or retrieve image hashes
    if not submission.image_hash_before:
        submission.image_hash_before = compute_image_hash(submission.before_photo)
    if not submission.image_hash_after:
        submission.image_hash_after = compute_image_hash(submission.after_photo)

    fraud_report = detect_evidence_fraud(
        before_hash=submission.image_hash_before,
        after_hash=submission.image_hash_after,
        current_user_id=submission.user_id,
        current_mission_id=submission.mission_id,
        exclude_submission_id=submission.id,
    )

    # Step 3 & 4: AI Analysis & Mission Matching
    verifier = get_ai_verifier()
    sub_dict = submission.to_dict()
    miss_dict = mission.to_dict()

    result = verifier.verify(
        submission=sub_dict,
        mission=miss_dict,
        fraud_report=fraud_report,
    )

    # Step 5: Save Verification Results
    submission.verification_status = result.status
    submission.confidence_score = result.confidence_score
    submission.evidence_relevance = result.evidence_relevance
    submission.before_after_comparison = result.before_after_comparison
    submission.detected_inconsistencies = result.detected_inconsistencies
    submission.verification_explanation = result.verification_explanation
    submission.ai_findings = json.dumps(result.ai_findings)
    submission.review_decision = result.review_decision
    submission.reviewed_by = result.reviewed_by
    submission.reviewed_at = result.reviewed_at
    submission.is_demo_verification = result.is_demo_verification

    if result.status == "Rejected":
        submission.rejection_reason = result.verification_explanation

    db.session.commit()

    # Step 6: XP Integration
    xp_result = None
    if result.status == "Verified" and auto_award_xp:
        xp_result = award_mission_xp(
            user_id=submission.user_id,
            submission_id=submission.id,
            mission_id=submission.mission_id,
            reviewer_note=f"Verified by {result.reviewed_by}",
        )

    return {
        "success": True,
        "status": submission.verification_status,
        "decision": submission.review_decision,
        "confidence_score": submission.confidence_score,
        "evidence_relevance": submission.evidence_relevance,
        "explanation": submission.verification_explanation,
        "is_demo": submission.is_demo_verification,
        "xp_award": xp_result,
        "submission": submission.to_dict(),
    }


def admin_review_submission(
    submission_id: int,
    admin_user: User,
    action: str,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Administrative manual review decision handler:
    - 'approve': Marks 'Verified', logs manual review, safely awards XP.
    - 'reject': Marks 'Rejected', records rejection reason, ensures NO XP.
    - 'request_evidence': Marks 'Requires Manual Review' with feedback request.
    """
    if not admin_user or not getattr(admin_user, "is_admin", False):
        return {"success": False, "error": "unauthorized", "message": "Administrator privileges required."}

    submission = db.session.get(Submission, submission_id)
    if not submission:
        return {"success": False, "error": "submission_not_found", "message": "Submission not found."}

    now = utc_now()
    reviewer_identifier = f"Admin: {admin_user.full_name} ({admin_user.email})"

    if action == "approve":
        submission.verification_status = "Verified"
        submission.review_decision = "manual_approved"
        submission.reviewed_by = reviewer_identifier
        submission.reviewed_at = now
        submission.admin_feedback = reason.strip() if reason else "Approved by administrator upon review."
        submission.rejection_reason = None
        db.session.commit()

        # Award XP upon manual verification
        xp_res = award_mission_xp(
            user_id=submission.user_id,
            submission_id=submission.id,
            mission_id=submission.mission_id,
            reviewer_note=f"Manually Approved by {admin_user.full_name}",
        )

        return {
            "success": True,
            "action": "approved",
            "message": f"Submission {submission.reference_id} approved successfully! XP awarded.",
            "xp_info": xp_res,
            "submission": submission.to_dict(),
        }

    elif action == "reject":
        clean_reason = reason.strip() if reason else "Submission does not satisfy mission criteria."
        submission.verification_status = "Rejected"
        submission.review_decision = "manual_rejected"
        submission.rejection_reason = clean_reason
        submission.admin_feedback = clean_reason
        submission.reviewed_by = reviewer_identifier
        submission.reviewed_at = now
        db.session.commit()

        return {
            "success": True,
            "action": "rejected",
            "message": f"Submission {submission.reference_id} rejected.",
            "submission": submission.to_dict(),
        }

    elif action == "request_evidence":
        feedback = reason.strip() if reason else "Please upload clearer camera evidence showing completed fieldwork."
        submission.verification_status = "Requires Manual Review"
        submission.review_decision = "additional_evidence_requested"
        submission.admin_feedback = feedback
        submission.rejection_reason = feedback
        submission.reviewed_by = reviewer_identifier
        submission.reviewed_at = now
        db.session.commit()

        return {
            "success": True,
            "action": "evidence_requested",
            "message": f"Additional evidence requested for submission {submission.reference_id}.",
            "submission": submission.to_dict(),
        }

    return {"success": False, "error": "invalid_action", "message": f"Unsupported review action: {action}"}


def get_user_submissions(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all submissions belonging to a specific member."""
    submissions = (
        Submission.query.filter_by(user_id=user_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    return [s.to_dict() for s in submissions]


def get_submission_by_id(submission_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve single submission with optional user ownership validation."""
    query = Submission.query.filter_by(id=submission_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    submission = query.first()
    if not submission:
        return None
    return submission.to_dict()


def get_all_submissions_for_admin(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all submissions in the system for administrative oversight."""
    query = Submission.query.order_by(Submission.submitted_at.desc())
    if status_filter and status_filter != "all":
        query = query.filter_by(verification_status=status_filter)
    submissions = query.all()
    return [s.to_dict() for s in submissions]


def can_user_access_evidence_file(user_id: int, filename: str) -> bool:
    """
    Check if an authenticated user owns the submission linked to an evidence file,
    or has administrative privileges to review community submissions.
    """
    if not user_id or not filename:
        return False

    user = db.session.get(User, user_id)
    if not user:
        return False

    # Administrators have global read permissions for evidence review
    if getattr(user, "is_admin", False):
        return True

    submission = (
        Submission.query.filter(
            (Submission.before_photo == filename)
            | (Submission.after_photo == filename)
            | (Submission.video_path == filename)
        )
        .first()
    )

    if not submission:
        return False

    return submission.user_id == user_id


def get_user_mission_history(
    user_id: int,
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve comprehensive mission participation history for a user.
    Includes all states:
    - Completed (Verified)
    - Under Review (Manual Review / Pending)
    - Rejected
    - In Progress (Accepted but not yet submitted)

    Each card provides:
    - Mission title
    - Mission category
    - Date accepted
    - Submission date (or 'Not submitted yet')
    - Current verification status
    - XP earned
    - Mission completion status
    - Thumbnail of submitted proof
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"items": [], "counts": {"total": 0, "completed": 0, "under_review": 0, "rejected": 0, "in_progress": 0}}

    # 1. Fetch all submissions by user
    submissions = (
        Submission.query.filter_by(user_id=user_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )

    # 2. Fetch all user accepted missions
    user_missions = (
        UserMission.query.filter_by(user_id=user_id)
        .order_by(UserMission.accepted_at.desc())
        .all()
    )
    user_missions_by_mission_id = {um.mission_id: um for um in user_missions}

    items = []
    seen_mission_ids = set()

    # Process all submissions
    for sub in submissions:
        mission = sub.mission
        if not mission:
            mission = db.session.get(Mission, sub.mission_id)
        if not mission:
            continue

        seen_mission_ids.add(sub.mission_id)
        um = user_missions_by_mission_id.get(sub.mission_id)
        accepted_date = um.accepted_at if um else sub.submitted_at

        # Determine verification & completion states
        v_status = sub.verification_status
        if um and um.status == "withdrawn":
            completion_status = "Withdrawn"
            display_status = "Withdrawn"
        elif v_status == "Verified":
            completion_status = "Completed"
            display_status = "Verified"
        elif v_status == "Rejected":
            completion_status = "Rejected"
            display_status = "Rejected"
        elif v_status == "Requires Manual Review":
            completion_status = "Under Review"
            display_status = "Manual Review"
        else:
            completion_status = "Under Review"
            display_status = "Pending"

        xp_earned = sub.xp_awarded_amount if sub.xp_awarded else 0

        thumb_url = f"/missions/evidence/{sub.before_photo}" if sub.before_photo else None

        items.append({
            "id": sub.id,
            "submission_id": sub.id,
            "reference_id": sub.reference_id,
            "mission_id": mission.id,
            "mission_title": mission.title,
            "mission_category": mission.category,
            "mission_slug": mission.slug,
            "mission_icon": mission.icon or "🌱",
            "date_accepted": accepted_date.strftime("%b %d, %Y") if accepted_date else "N/A",
            "date_accepted_raw": accepted_date,
            "submission_date": sub.submitted_at.strftime("%b %d, %Y %I:%M %p") if sub.submitted_at else "N/A",
            "submission_date_raw": sub.submitted_at,
            "verification_status": display_status,
            "raw_verification_status": v_status,
            "xp_earned": xp_earned,
            "mission_completion_status": completion_status,
            "thumbnail_url": thumb_url,
            "before_photo": sub.before_photo,
            "after_photo": sub.after_photo,
            "video_path": sub.video_path,
            "description": sub.description,
            "confidence_score": sub.confidence_score,
            "verification_explanation": sub.verification_explanation,
            "admin_feedback": sub.admin_feedback or (sub.rejection_reason if sub.review_decision and "manual" in sub.review_decision else None),
            "has_submission": True,
            "detail_url": f"/missions/history/{sub.id}",
        })

    # Process accepted missions with no submission yet (In Progress or Withdrawn)
    for um in user_missions:
        if um.mission_id not in seen_mission_ids:
            mission = um.mission
            if not mission:
                mission = db.session.get(Mission, um.mission_id)
            if not mission:
                continue

            if um.status == "withdrawn":
                items.append({
                    "id": None,
                    "submission_id": None,
                    "reference_id": f"WITHDRAWN-M{mission.id:04d}",
                    "mission_id": mission.id,
                    "mission_title": mission.title,
                    "mission_category": mission.category,
                    "mission_slug": mission.slug,
                    "mission_icon": mission.icon or "🌱",
                    "date_accepted": um.accepted_at.strftime("%b %d, %Y") if um.accepted_at else "N/A",
                    "date_accepted_raw": um.accepted_at,
                    "submission_date": "Withdrawn",
                    "submission_date_raw": None,
                    "verification_status": "Withdrawn",
                    "raw_verification_status": "withdrawn",
                    "xp_earned": 0,
                    "mission_completion_status": "Withdrawn",
                    "thumbnail_url": None,
                    "before_photo": None,
                    "after_photo": None,
                    "video_path": None,
                    "description": None,
                    "confidence_score": None,
                    "verification_explanation": "Mission participation withdrawn by user.",
                    "admin_feedback": None,
                    "has_submission": False,
                    "detail_url": f"/missions/{mission.slug}",
                    "submit_url": None,
                })
            elif um.status in ["accepted", "in_progress"]:
                items.append({
                    "id": None,
                    "submission_id": None,
                    "reference_id": f"ACTIVE-M{mission.id:04d}",
                    "mission_id": mission.id,
                    "mission_title": mission.title,
                    "mission_category": mission.category,
                    "mission_slug": mission.slug,
                    "mission_icon": mission.icon or "🌱",
                    "date_accepted": um.accepted_at.strftime("%b %d, %Y") if um.accepted_at else "N/A",
                    "date_accepted_raw": um.accepted_at,
                    "submission_date": "Not submitted yet",
                    "submission_date_raw": None,
                    "verification_status": "In Progress",
                    "raw_verification_status": "in_progress",
                    "xp_earned": 0,
                    "mission_completion_status": "In Progress",
                    "thumbnail_url": None,
                    "before_photo": None,
                    "after_photo": None,
                    "video_path": None,
                    "description": None,
                    "confidence_score": None,
                    "verification_explanation": None,
                    "admin_feedback": None,
                    "has_submission": False,
                    "detail_url": f"/missions/{mission.slug}",
                    "submit_url": f"/missions/{mission.slug}/submit",
                })

    # Sort all items by most recent activity
    def get_sort_key(item):
        return item["submission_date_raw"] or item["date_accepted_raw"] or datetime.min

    items.sort(key=get_sort_key, reverse=True)

    # Compute quick counters across all items
    counts = {
        "total": len(items),
        "completed": len([i for i in items if i["mission_completion_status"] == "Completed"]),
        "under_review": len([i for i in items if i["mission_completion_status"] == "Under Review"]),
        "rejected": len([i for i in items if i["mission_completion_status"] == "Rejected"]),
        "in_progress": len([i for i in items if i["mission_completion_status"] == "In Progress"]),
        "withdrawn": len([i for i in items if i["mission_completion_status"] == "Withdrawn" or i["verification_status"] == "Withdrawn"]),
    }

    # Filter if requested
    filtered_items = items
    if status_filter and status_filter.lower() != "all":
        norm_filter = status_filter.strip().lower()
        if norm_filter in ["completed", "verified"]:
            filtered_items = [i for i in items if i["mission_completion_status"] == "Completed"]
        elif norm_filter in ["under_review", "under-review", "review", "manual_review", "pending"]:
            filtered_items = [i for i in items if i["mission_completion_status"] == "Under Review"]
        elif norm_filter in ["rejected"]:
            filtered_items = [i for i in items if i["mission_completion_status"] == "Rejected"]
        elif norm_filter in ["in_progress", "in-progress", "ongoing"]:
            filtered_items = [i for i in items if i["mission_completion_status"] == "In Progress"]
        elif norm_filter in ["withdrawn"]:
            filtered_items = [i for i in items if i["mission_completion_status"] == "Withdrawn" or i["verification_status"] == "Withdrawn"]

    return {
        "items": filtered_items,
        "all_items": items,
        "counts": counts,
        "active_filter": status_filter or "all",
    }


def get_detailed_mission_submission(
    submission_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve comprehensive 13-point detailed submission record:
    1. Mission title and description
    2. Instructions and requirements
    3. Date accepted
    4. Submission date and time
    5. Before-and-after photographs
    6. Optional video evidence (if available)
    7. GPS location (if recorded)
    8. Current verification status
    9. AI confidence score
    10. Short verification explanation
    11. Administrator feedback (if reviewed)
    12. XP awarded
    13. Submission history and status changes
    """
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return None

    # Strict access control: only submission owner or platform administrator
    if submission.user_id != user_id and not is_admin:
        raise PermissionError("Access forbidden: You do not own this submission record.")

    mission = submission.mission
    if not mission:
        mission = db.session.get(Mission, submission.mission_id)

    # Date accepted lookup
    um = UserMission.query.filter_by(
        user_id=submission.user_id,
        mission_id=submission.mission_id,
    ).first()
    accepted_at = um.accepted_at if um else submission.submitted_at

    # Build chronological status timeline
    timeline = []

    # 1. Mission Accepted
    timeline.append({
        "step": 1,
        "title": "Mission Accepted",
        "badge": "Enrolled",
        "icon": "🎯",
        "timestamp": accepted_at.strftime("%b %d, %Y %I:%M %p") if accepted_at else "N/A",
        "timestamp_raw": accepted_at,
        "description": f"Accepted mission '{mission.title}' in the {mission.category} track.",
    })

    # 2. Evidence Submitted
    timeline.append({
        "step": 2,
        "title": "Camera Proof Submitted",
        "badge": "Submitted",
        "icon": "📸",
        "timestamp": submission.submitted_at.strftime("%b %d, %Y %I:%M %p") if submission.submitted_at else "N/A",
        "timestamp_raw": submission.submitted_at,
        "description": (
            f"Captured before & after camera photographs"
            + (f" with GPS verification (±{int(submission.location_accuracy)}m)" if submission.latitude and submission.location_accuracy else "")
            + (", and video evidence" if submission.video_path else "")
            + "."
        ),
    })

    # 3. AI / Heuristic Verification
    if submission.reviewed_at or submission.verification_status in ["Verified", "Rejected", "Requires Manual Review"]:
        review_time = submission.reviewed_at or submission.submitted_at
        if submission.verification_status == "Verified":
            timeline.append({
                "step": 3,
                "title": "Evidence Verified",
                "badge": "Verified",
                "icon": "✅",
                "timestamp": review_time.strftime("%b %d, %Y %I:%M %p"),
                "timestamp_raw": review_time,
                "description": submission.verification_explanation or f"Verified with {submission.confidence_score}% confidence score.",
            })
            if submission.xp_awarded:
                timeline.append({
                    "step": 4,
                    "title": "XP Reward Dispatched",
                    "badge": f"+{submission.xp_awarded_amount} XP",
                    "icon": "🌟",
                    "timestamp": review_time.strftime("%b %d, %Y %I:%M %p"),
                    "timestamp_raw": review_time,
                    "description": f"Successfully credited +{submission.xp_awarded_amount} XP to member's eco-profile.",
                })
        elif submission.verification_status == "Rejected":
            timeline.append({
                "step": 3,
                "title": "Verification Rejected",
                "badge": "Rejected",
                "icon": "❌",
                "timestamp": review_time.strftime("%b %d, %Y %I:%M %p"),
                "timestamp_raw": review_time,
                "description": submission.rejection_reason or submission.verification_explanation or "Submission did not satisfy mission requirements.",
            })
        elif submission.verification_status == "Requires Manual Review":
            timeline.append({
                "step": 3,
                "title": "Escalated for Manual Review",
                "badge": "Under Review",
                "icon": "⚠️",
                "timestamp": review_time.strftime("%b %d, %Y %I:%M %p"),
                "timestamp_raw": review_time,
                "description": submission.verification_explanation or "Confidence threshold or anti-signals require administrator review.",
            })
    else:
        timeline.append({
            "step": 3,
            "title": "Verification In Progress",
            "badge": "Pending",
            "icon": "⏳",
            "timestamp": submission.submitted_at.strftime("%b %d, %Y %I:%M %p") if submission.submitted_at else "N/A",
            "timestamp_raw": submission.submitted_at,
            "description": "Evidence awaiting verification processing.",
        })

    # 4. Administrator Feedback (if recorded)
    admin_feedback_note = submission.admin_feedback or (
        submission.rejection_reason if submission.review_decision and "manual" in submission.review_decision else None
    )
    if admin_feedback_note and submission.review_decision and "manual" in submission.review_decision:
        timeline.append({
            "step": len(timeline) + 1,
            "title": "Administrator Manual Review",
            "badge": "Admin Decision",
            "icon": "📋",
            "timestamp": (submission.reviewed_at or submission.submitted_at).strftime("%b %d, %Y %I:%M %p"),
            "timestamp_raw": submission.reviewed_at or submission.submitted_at,
            "description": admin_feedback_note,
        })

    return {
        # 1. Mission title and description
        "mission_id": mission.id,
        "mission_title": mission.title,
        "mission_description": mission.why_it_matters or mission.instructions or "",
        "mission_category": mission.category,
        "mission_slug": mission.slug,
        "mission_icon": mission.icon or "🌱",
        "difficulty": mission.difficulty,
        "duration": mission.duration,

        # 2. Instructions and requirements
        "instructions": mission.instructions,
        "proof_requirements": mission.proof_requirements,
        "safety_guidelines": mission.safety_guidelines,

        # 3. Date accepted
        "date_accepted": accepted_at.strftime("%b %d, %Y %I:%M %p") if accepted_at else "N/A",
        "date_accepted_raw": accepted_at,

        # 4. Submission date and time
        "submission_id": submission.id,
        "reference_id": submission.reference_id,
        "submission_date": submission.submitted_at.strftime("%b %d, %Y %I:%M %p") if submission.submitted_at else "N/A",
        "submission_date_raw": submission.submitted_at,
        "capture_timestamp": submission.capture_timestamp.strftime("%b %d, %Y %I:%M %p") if submission.capture_timestamp else None,
        "field_notes": submission.description,

        # 5. Before-and-after photographs
        "before_photo": submission.before_photo,
        "before_photo_url": f"/missions/evidence/{submission.before_photo}" if submission.before_photo else None,
        "after_photo": submission.after_photo,
        "after_photo_url": f"/missions/evidence/{submission.after_photo}" if submission.after_photo else None,

        # 6. Optional video evidence
        "video_path": submission.video_path,
        "video_url": f"/missions/evidence/{submission.video_path}" if submission.video_path else None,

        # 7. GPS location
        "gps_recorded": bool(submission.latitude and submission.longitude),
        "latitude": submission.latitude,
        "longitude": submission.longitude,
        "location_accuracy": submission.location_accuracy,

        # 8. Current verification status
        "verification_status": submission.verification_status,
        "display_status": "Manual Review" if submission.verification_status == "Requires Manual Review" else submission.verification_status,

        # 9. AI confidence score
        "confidence_score": submission.confidence_score,

        # 10. Short verification explanation
        "verification_explanation": submission.verification_explanation,

        # 11. Administrator feedback
        "admin_feedback": admin_feedback_note,

        # 12. XP awarded
        "xp_awarded": submission.xp_awarded,
        "xp_awarded_amount": submission.xp_awarded_amount,

        # 13. Submission history and status changes
        "timeline": timeline,

        # Additional metadata
        "review_decision": submission.review_decision,
        "reviewed_by": submission.reviewed_by,
        "reviewed_at": submission.reviewed_at.strftime("%b %d, %Y %I:%M %p") if submission.reviewed_at else None,
        "is_demo_verification": submission.is_demo_verification,
        "user_id": submission.user_id,
    }
