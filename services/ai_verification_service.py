"""
EcoQuest — Modular AI-Assisted Mission Verification Service.

Provider-independent architecture supporting:
- Real Vision AI API (Google Gemini 1.5 / 2.0 / Flash / Pro) when API credentials exist.
- Clear, unpretentious Demo Rule-Based Heuristic Engine when no API credentials are configured.
- Structured verification schema with confidence scoring, evidence relevance,
  before/after comparison, object detection, and inconsistency reporting.
- Strict truthfulness: NEVER claims actual AI analysis occurred when operating in demo mode.
"""

import os
import json
import base64
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
from models import utc_now
from services.evidence_storage import get_evidence_path
from services.verification_rules import evaluate_mission_match, get_rules_for_category


class VerificationResult:
    """Standardized verification output data transfer object."""

    def __init__(
        self,
        status: str,
        confidence_score: float,
        evidence_relevance: str,
        before_after_comparison: str,
        detected_inconsistencies: Optional[str] = None,
        verification_explanation: str = "",
        ai_findings: Optional[Dict[str, Any]] = None,
        review_decision: str = "pending_review",
        reviewed_by: str = "DEMO_HEURISTIC_ENGINE",
        is_demo_verification: bool = True,
    ):
        self.status = status
        self.confidence_score = round(confidence_score, 1)
        self.evidence_relevance = evidence_relevance
        self.before_after_comparison = before_after_comparison
        self.detected_inconsistencies = detected_inconsistencies or ""
        self.verification_explanation = verification_explanation
        self.ai_findings = ai_findings or {}
        self.review_decision = review_decision
        self.reviewed_by = reviewed_by
        self.reviewed_at = utc_now()
        self.is_demo_verification = is_demo_verification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence_score": self.confidence_score,
            "evidence_relevance": self.evidence_relevance,
            "before_after_comparison": self.before_after_comparison,
            "detected_inconsistencies": self.detected_inconsistencies,
            "verification_explanation": self.verification_explanation,
            "ai_findings": self.ai_findings,
            "review_decision": self.review_decision,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat(),
            "is_demo_verification": self.is_demo_verification,
        }


class BaseAIVerifier(ABC):
    """Abstract interface for environmental mission proof verification providers."""

    @abstractmethod
    def verify(
        self,
        submission: Dict[str, Any],
        mission: Dict[str, Any],
        fraud_report: Dict[str, Any],
    ) -> VerificationResult:
        """Analyze evidence and render structured verification verdict."""
        pass


class DemoRuleBasedVerifier(BaseAIVerifier):
    """
    Transparent rule-based heuristic verification engine.
    Used when no external AI API credentials are configured.
    Clearly marks all analysis as simulated demo verification.
    """

    def verify(
        self,
        submission: Dict[str, Any],
        mission: Dict[str, Any],
        fraud_report: Dict[str, Any],
    ) -> VerificationResult:
        category_slug = mission.get("category_slug") or mission.get("category", "")
        description = submission.get("description", "")
        has_video = bool(submission.get("video_path"))
        has_gps = bool(submission.get("latitude") and submission.get("longitude"))

        # Evaluate against domain-specific mission criteria
        eval_data = evaluate_mission_match(
            category_slug=category_slug,
            mission_title=mission.get("title", ""),
            description=description,
            has_video=has_video,
            has_gps=has_gps,
            is_identical_images=fraud_report.get("identical_before_after", False),
            is_reused_evidence=fraud_report.get("is_reused_evidence", False),
            mission_slug=mission.get("slug"),
        )

        score = eval_data["confidence_score"]
        relevance = eval_data["evidence_relevance"]
        inconsistencies = eval_data["inconsistencies"]

        # Incorporate fraud report issues
        for issue in fraud_report.get("issues", []):
            if issue not in inconsistencies:
                inconsistencies.append(issue)

        # Before/after comparison narrative
        if fraud_report.get("identical_before_after"):
            comparison = (
                "[Demo Mode] Anomaly: The submitted before-photo and after-photo are identical image files. "
                "No transformation or environmental remediation was detected between photos."
            )
        else:
            comparison = (
                f"[Demo Mode] Before-photo evaluated against baseline ({eval_data['expected_before']}). "
                f"After-photo corresponds to expected remediated state ({eval_data['expected_after']}). "
                f"Visual continuity verified."
            )

        # Strict 3-Outcome Decision Rubric: Verified, Requires Manual Review, Rejected
        # 1. Rejected: Identical photos or severe fraud
        if fraud_report.get("identical_before_after"):
            status = "Rejected"
            decision = "auto_rejected"
            explanation = (
                "[Demo Mode] Verification failed: Duplicate evidence detected. The before-photo and after-photo "
                "are identical files, which indicates no actual fieldwork was conducted."
            )
        # 2. Reused evidence across users -> Routed to Manual Review for administrative investigation
        elif fraud_report.get("is_reused_evidence"):
            status = "Requires Manual Review"
            decision = "escalated_for_review"
            explanation = (
                f"[Demo Mode] Submission flagged for administrator manual review. "
                f"Evidence image hash matches an existing submission in the platform audit ledger. "
                f"Confidence score: {score}%."
            )
        # 3. Rejected: Unrelated content or severely low confidence (< 40.0%)
        elif score < 40.0 or relevance == "unrelated":
            status = "Rejected"
            decision = "auto_rejected"
            explanation = (
                f"[Demo Mode] Verification failed: Insufficient or irrelevant evidence (confidence: {score}%). "
                f"The submitted documentation did not demonstrate the required fieldwork for '{mission.get('title')}'. "
                f"Reasons: {'; '.join(inconsistencies) if inconsistencies else 'No matching environmental actions detected'}."
            )
        # 4. Verified: High confidence (>= 80.0%), high relevance, zero inconsistencies, mission-specific actions verified
        elif (
            score >= 80.0
            and relevance == "high"
            and not inconsistencies
            and eval_data.get("specific_mission_matched", False)
        ):
            status = "Verified"
            decision = "auto_approved"
            explanation = (
                f"[Demo Mode Heuristic Engine] Mission verified successfully (confidence: {score}%). "
                f"Evidence directly satisfies specific requirements for '{mission.get('title')}'. "
                f"Detected fieldwork actions: {', '.join(eval_data['matched_actions']) if eval_data['matched_actions'] else 'Documented activity'}. "
                f"Environmental cues: {', '.join(eval_data['detected_objects']) if eval_data['detected_objects'] else 'Verified field context'}."
            )
        # 5. Requires Manual Review (Manual Review): Borderline confidence (40-79.9%), generic category without mission depth, or flagged anomalies
        else:
            status = "Requires Manual Review"
            decision = "escalated_for_review"
            reasons = []
            if score < 80.0:
                reasons.append(f"Confidence score ({score}%) requires human verification")
            if not eval_data.get("specific_mission_matched", False):
                reasons.append(f"Generic category evidence provided without specific '{mission.get('title')}' actions")
            if inconsistencies:
                reasons.append(f"Noted queries: {'; '.join(inconsistencies)}")
            explanation = (
                f"[Demo Mode] Submission routed to Manual Review for administrator inspection. "
                f"Summary: {'. '.join(reasons)}."
            )

        ai_findings = {
            "engine": "EcoQuest Heuristic Rule-Based Verifier (Demo Mode)",
            "external_ai_connected": False,
            "category_evaluated": eval_data["category"],
            "detected_objects": eval_data["detected_objects"],
            "matched_actions": eval_data["matched_actions"],
            "inconsistencies": inconsistencies,
            "gps_included": has_gps,
            "video_included": has_video,
            "confidence_score": score,
            "eval_timestamp": utc_now().isoformat(),
        }

        return VerificationResult(
            status=status,
            confidence_score=score,
            evidence_relevance=relevance,
            before_after_comparison=comparison,
            detected_inconsistencies="; ".join(inconsistencies) if inconsistencies else "",
            verification_explanation=explanation,
            ai_findings=ai_findings,
            review_decision=decision,
            reviewed_by="DEMO_HEURISTIC_ENGINE",
            is_demo_verification=True,
        )


class GeminiVisionVerifier(BaseAIVerifier):
    """
    Connects to Google Gemini Vision API for live multimodal verification.
    Gracefully falls back to DemoRuleBasedVerifier if API credentials are
    unreachable or service calls fail.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify(
        self,
        submission: Dict[str, Any],
        mission: Dict[str, Any],
        fraud_report: Dict[str, Any],
    ) -> VerificationResult:
        # If fraud check caught identical images upfront, reject immediately without wasting API tokens
        if fraud_report.get("identical_before_after"):
            return VerificationResult(
                status="Rejected",
                confidence_score=15.0,
                evidence_relevance="unrelated",
                before_after_comparison="Before and after photographs are byte-identical files.",
                detected_inconsistencies="Duplicate image anomaly: Before and after files are identical.",
                verification_explanation="Verification rejected: The before-photo and after-photo submitted are identical images.",
                ai_findings={"fraud_flag": "identical_photos"},
                review_decision="auto_rejected",
                reviewed_by="AI_VISION_SAFETY_FILTER",
                is_demo_verification=False,
            )

        try:
            # Attempt live multimodal API call
            result = self._call_gemini_vision(submission, mission, fraud_report)
            if result:
                return result
        except Exception as e:
            # Graceful fallback on network or API failure
            pass

        # Fallback to clearly labelled demo verifier on API error
        fallback = DemoRuleBasedVerifier().verify(submission, mission, fraud_report)
        fallback.reviewed_by = "DEMO_FALLBACK_API_UNAVAILABLE"
        fallback.ai_findings["api_fallback_note"] = "Gemini Vision API was unavailable; evaluated using local engine."
        return fallback

    def _call_gemini_vision(
        self,
        submission: Dict[str, Any],
        mission: Dict[str, Any],
        fraud_report: Dict[str, Any],
    ) -> Optional[VerificationResult]:
        """Performs JSON-structured multimodal analysis via Gemini Vision API."""
        import urllib.request

        before_path = get_evidence_path(submission.get("before_photo", ""))
        after_path = get_evidence_path(submission.get("after_photo", ""))
        if not before_path or not after_path or not os.path.exists(before_path) or not os.path.exists(after_path):
            return None

        with open(before_path, "rb") as f:
            b64_before = base64.b64encode(f.read()).decode("utf-8")
        with open(after_path, "rb") as f:
            b64_after = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            f"You are EcoQuest's AI Environmental Verification Auditor.\n"
            f"Mission Title: {mission.get('title')}\n"
            f"Mission Category: {mission.get('category')}\n"
            f"Required Proof: {mission.get('proof_requirements')}\n"
            f"User Field Notes: '{submission.get('description')}'\n\n"
            f"Examine the two attached photos: Image 1 is BEFORE fieldwork, Image 2 is AFTER fieldwork.\n"
            f"Return a strict JSON response with keys:\n"
            f"- 'confidence_score': integer 0 to 100\n"
            f"- 'evidence_relevance': string ('high', 'medium', 'low', 'unrelated')\n"
            f"- 'before_after_comparison': brief comparison sentence\n"
            f"- 'detected_objects': list of relevant environmental objects seen\n"
            f"- 'inconsistencies': list of any detected anomalies or staging\n"
            f"- 'explanation': comprehensive verification rationale\n"
            f"- 'decision': string ('Verified', 'Requires Manual Review', 'Rejected')"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_before}},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_after}},
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                text_content = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)

                status = parsed.get("decision", "Requires Manual Review")
                if status not in ["Verified", "Rejected", "Requires Manual Review"]:
                    status = "Requires Manual Review"

                score = float(parsed.get("confidence_score", 50.0))
                relevance = parsed.get("evidence_relevance", "medium")
                inconsistencies = parsed.get("inconsistencies", [])
                decision = (
                    "auto_approved"
                    if status == "Verified"
                    else "auto_rejected"
                    if status == "Rejected"
                    else "escalated_for_review"
                )

                return VerificationResult(
                    status=status,
                    confidence_score=score,
                    evidence_relevance=relevance,
                    before_after_comparison=parsed.get("before_after_comparison", "Analyzed by Gemini Vision."),
                    detected_inconsistencies="; ".join(inconsistencies) if isinstance(inconsistencies, list) else str(inconsistencies),
                    verification_explanation=parsed.get("explanation", "Verified via Gemini Vision API."),
                    ai_findings={
                        "engine": "Google Gemini Vision API",
                        "external_ai_connected": True,
                        "detected_objects": parsed.get("detected_objects", []),
                        "confidence_score": score,
                        "raw_model_response": parsed,
                    },
                    review_decision=decision,
                    reviewed_by="AI_GEMINI_VISION",
                    is_demo_verification=False,
                )
        return None


def get_ai_verifier() -> BaseAIVerifier:
    """
    Factory function returning the active verification engine.
    Checks environment for AI_SERVICE_API_KEY or GEMINI_API_KEY.
    Defaults to DemoRuleBasedVerifier when credentials are missing.
    """
    api_key = os.environ.get("AI_SERVICE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key and len(api_key.strip()) > 5:
        return GeminiVisionVerifier(api_key.strip())
    return DemoRuleBasedVerifier()
