"""
EcoQuest — Data Models Package.

Implements database entities using Flask-SQLAlchemy.
Safe, modular, and prepared for future Supabase migration.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utc_now():
    """Return timezone-naive UTC datetime for consistent database timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """
    User entity representing registered community members.
    Never stores plaintext passwords.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    college = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(
        db.String(255), nullable=True, default="default-avatar.svg"
    )
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    total_xp = db.Column(db.Integer, default=0, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    otps = db.relationship(
        "OTPVerification",
        backref="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str):
        """Hash and store a secure password hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify candidate password against the stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def avatar_url(self) -> str:
        """Return the secure authenticated proxy URL or default image path."""
        if not self.profile_picture or self.profile_picture == "default-avatar.svg":
            return "/static/images/default-avatar.svg"
        raw = self.profile_picture
        if "/" in raw:
            raw = raw.rsplit("/", 1)[-1]
        return f"/profile/avatar/{raw}"

    @property
    def is_demo(self) -> bool:
        """Indicate whether this account is a demonstration / test fixture."""
        em = (self.email or "").lower()
        fn = (self.full_name or "").lower()
        return "demo" in em or "test" in em or "demo" in fn or "sample" in fn

    def to_dict(self):
        """Serialize safe public fields."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "city": self.city,
            "college": self.college,
            "profile_picture": self.avatar_url,
            "email_verified": self.email_verified,
            "phone_verified": self.phone_verified,
            "total_xp": self.total_xp,
            "is_admin": self.is_admin,
            "is_demo": self.is_demo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.id}: {self.email}>"


class OTPVerification(db.Model):
    """
    Stores 6-digit one-time passcodes with expiration and usage status.
    """

    __tablename__ = "otp_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(30), default="email_verification", nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def is_expired(self) -> bool:
        """Check whether this OTP has passed its expiration time."""
        return utc_now() > self.expires_at

    def __repr__(self):
        return f"<OTPVerification user={self.user_id} purpose={self.purpose} used={self.used}>"


class LessonCategory(db.Model):
    """
    Environmental learning categories (e.g. Climate Change, Waste Management).
    """

    __tablename__ = "lesson_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, index=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), default="🌿", nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    lessons = db.relationship(
        "Lesson",
        backref="category",
        cascade="all, delete-orphan",
        order_by="Lesson.order",
        lazy="select",
    )

    def to_dict(self):
        """Serialize category data."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "icon": self.icon,
            "order": self.order,
            "lessons_count": len(self.lessons) if self.lessons else 0,
        }

    def __repr__(self):
        return f"<LessonCategory {self.slug}>"


class Lesson(db.Model):
    """
    Educational lesson entity with rich content sections, facts, takeaways, and quiz.
    """

    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("lesson_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    introduction = db.Column(db.Text, nullable=False)
    estimated_minutes = db.Column(db.Integer, default=5, nullable=False)
    xp_reward = db.Column(db.Integer, default=50, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)
    icon = db.Column(db.String(50), default="🌱", nullable=False)

    # Structured sections, facts, takeaways
    content_sections = db.Column(db.JSON, nullable=False)
    important_facts = db.Column(db.JSON, nullable=False)
    key_takeaways = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    questions = db.relationship(
        "QuizQuestion",
        backref="lesson",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.order",
        lazy="select",
    )
    progress_records = db.relationship(
        "LessonProgress",
        backref="lesson",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    quiz_attempts = db.relationship(
        "QuizAttempt",
        backref="lesson",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self):
        """Serialize safe public fields."""
        return {
            "id": self.id,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "category_slug": self.category.slug if self.category else "",
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "estimated_minutes": self.estimated_minutes,
            "xp_reward": self.xp_reward,
            "order": self.order,
            "icon": self.icon,
            "questions_count": len(self.questions) if self.questions else 0,
        }

    def __repr__(self):
        return f"<Lesson {self.slug}>"


class QuizQuestion(db.Model):
    """
    Multiple-choice question attached to a lesson.
    """

    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_text = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)

    options = db.relationship(
        "QuizOption",
        backref="question",
        cascade="all, delete-orphan",
        order_by="QuizOption.order",
        lazy="select",
    )

    def to_dict(self, include_correct=False):
        """Serialize question with options."""
        return {
            "id": self.id,
            "question_text": self.question_text,
            "order": self.order,
            "explanation": self.explanation if include_correct else None,
            "options": [opt.to_dict(include_correct=include_correct) for opt in self.options],
        }

    def __repr__(self):
        return f"<QuizQuestion {self.id} for lesson {self.lesson_id}>"


class QuizOption(db.Model):
    """
    Single choice option for a quiz question.
    """

    __tablename__ = "quiz_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self, include_correct=False):
        """Serialize option."""
        data = {
            "id": self.id,
            "option_text": self.option_text,
            "order": self.order,
        }
        if include_correct:
            data["is_correct"] = self.is_correct
        return data

    def __repr__(self):
        return f"<QuizOption {self.id} (correct={self.is_correct})>"


class LessonProgress(db.Model):
    """
    Tracks member progress per lesson, completion state, and XP award status.
    """

    __tablename__ = "lesson_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.String(30), default="not_started", nullable=False
    )  # not_started, in_progress, completed
    completed = db.Column(db.Boolean, default=False, nullable=False)
    xp_awarded = db.Column(db.Boolean, default=False, nullable=False)
    highest_score = db.Column(db.Float, default=0.0, nullable=False)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )

    user = db.relationship(
        "User",
        backref=db.backref("lesson_progresses", cascade="all, delete-orphan", lazy="dynamic"),
    )

    def to_dict(self):
        """Serialize progress record."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "lesson_id": self.lesson_id,
            "status": self.status,
            "completed": self.completed,
            "xp_awarded": self.xp_awarded,
            "highest_score": self.highest_score,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return (
            f"<LessonProgress user={self.user_id} lesson={self.lesson_id} completed={self.completed}>"
        )


class QuizAttempt(db.Model):
    """
    Historical log of each quiz submission with score, answers, and pass/fail.
    """

    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score = db.Column(db.Float, nullable=False)  # percentage e.g. 75.0, 100.0
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, default=False, nullable=False)
    user_answers = db.Column(db.JSON, nullable=True)
    attempted_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("quiz_attempts", cascade="all, delete-orphan", lazy="dynamic"),
    )

    def to_dict(self):
        """Serialize attempt log."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "lesson_id": self.lesson_id,
            "score": self.score,
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "passed": self.passed,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
        }

    def __repr__(self):
        return f"<QuizAttempt user={self.user_id} lesson={self.lesson_id} score={self.score} passed={self.passed}>"


class Mission(db.Model):
    """
    Environmental actionable mission (e.g. cleanup, tree planting, recycling audit).
    """

    __tablename__ = "missions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(350), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    category_slug = db.Column(db.String(50), nullable=False, index=True)
    difficulty = db.Column(db.String(30), nullable=False)  # Beginner, Intermediate, Advanced
    duration = db.Column(db.String(50), nullable=False)
    xp_reward = db.Column(db.Integer, default=150, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    why_it_matters = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.JSON, nullable=False)  # List of step strings
    proof_requirements = db.Column(db.Text, nullable=False)
    safety_guidelines = db.Column(db.JSON, nullable=False)  # List of safety guideline strings
    image = db.Column(db.String(255), default="mission-cleanup.svg", nullable=False)
    icon = db.Column(db.String(50), default="🌱", nullable=False)
    allow_repeat = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    user_missions = db.relationship(
        "UserMission",
        backref="mission",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def completions_count(self) -> int:
        """Count of verified completed runs for this mission."""
        return self.user_missions.filter_by(status="completed").count()

    @property
    def participants_count(self) -> int:
        """Total distinct users who accepted or completed this mission."""
        return self.user_missions.count()

    def to_dict(self):
        """Serialize safe public fields."""
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "short_description": self.short_description,
            "category": self.category,
            "category_slug": self.category_slug,
            "difficulty": self.difficulty,
            "duration": self.duration,
            "xp_reward": self.xp_reward,
            "location": self.location,
            "why_it_matters": self.why_it_matters,
            "instructions": self.instructions,
            "proof_requirements": self.proof_requirements,
            "safety_guidelines": self.safety_guidelines,
            "image": self.image,
            "icon": self.icon,
            "allow_repeat": self.allow_repeat,
            "is_active": self.is_active,
            "completions_count": self.completions_count,
            "participants_count": self.participants_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Mission {self.id}: {self.title}>"


class UserMission(db.Model):
    """
    Tracks member participation in an environmental mission.
    Statuses: 'accepted', 'in_progress', 'completed'
    """

    __tablename__ = "user_missions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mission_id = db.Column(
        db.Integer,
        db.ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.String(30), default="accepted", nullable=False
    )  # accepted, in_progress, completed
    accepted_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        "User",
        backref=db.backref("user_missions", cascade="all, delete-orphan", lazy="dynamic"),
    )

    def to_dict(self):
        """Serialize user mission progress."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mission_id": self.mission_id,
            "status": self.status,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "mission": self.mission.to_dict() if self.mission else None,
        }

    def __repr__(self):
        return f"<UserMission user={self.user_id} mission={self.mission_id} status={self.status}>"


class Submission(db.Model):
    """
    Direct camera-captured proof submission for an environmental mission.
    Never exposes evidence publicly; served only via authenticated routes.
    """

    __tablename__ = "submissions"

    VALID_STATUSES = [
        "Pending",
        "Processing",
        "Pending Verification",
        "Verified",
        "Rejected",
        "Requires Manual Review",
        "Draft",
        "Submitted",
    ]

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mission_id = db.Column(
        db.Integer,
        db.ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    before_photo = db.Column(db.String(255), nullable=False)
    after_photo = db.Column(db.String(255), nullable=False)
    video_path = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_accuracy = db.Column(db.Float, nullable=True)  # in meters
    capture_timestamp = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    verification_status = db.Column(
        db.String(40), default="Pending", nullable=False, index=True
    )
    rejection_reason = db.Column(db.Text, nullable=True)

    # AI Verification & Telemetry Results
    confidence_score = db.Column(db.Float, nullable=True)
    evidence_relevance = db.Column(db.String(50), nullable=True)  # high, medium, low, unrelated
    before_after_comparison = db.Column(db.Text, nullable=True)
    detected_inconsistencies = db.Column(db.Text, nullable=True)
    verification_explanation = db.Column(db.Text, nullable=True)
    ai_findings = db.Column(db.Text, nullable=True)  # JSON-encoded findings & detected objects
    review_decision = db.Column(db.String(50), nullable=True)  # auto_approved, auto_rejected, manual_approved, manual_rejected, escalated_for_review
    reviewed_by = db.Column(db.String(100), nullable=True)  # AI_GEMINI_VISION, DEMO_VERIFIER_SIMULATED, admin user
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Fraud Prevention & Hashing
    image_hash_before = db.Column(db.String(64), nullable=True, index=True)
    image_hash_after = db.Column(db.String(64), nullable=True, index=True)
    is_demo_verification = db.Column(db.Boolean, default=False, nullable=False)
    admin_feedback = db.Column(db.Text, nullable=True)

    # XP Award Tracking
    xp_awarded = db.Column(db.Boolean, default=False, nullable=False)
    xp_awarded_amount = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    user = db.relationship(
        "User",
        backref=db.backref("submissions", cascade="all, delete-orphan", lazy="dynamic"),
    )
    mission = db.relationship(
        "Mission",
        backref=db.backref("submissions", cascade="all, delete-orphan", lazy="dynamic"),
    )

    @property
    def reference_id(self) -> str:
        """Formatted human-readable reference, e.g. SUB-00042."""
        return f"SUB-{self.id:05d}"

    def to_dict(self):
        """Serialize submission details."""
        return {
            "id": self.id,
            "reference_id": self.reference_id,
            "user_id": self.user_id,
            "mission_id": self.mission_id,
            "mission_title": self.mission.title if self.mission else "",
            "mission_category": self.mission.category if self.mission else "",
            "before_photo": self.before_photo,
            "after_photo": self.after_photo,
            "video_path": self.video_path,
            "before_photo_url": f"/missions/evidence/{self.before_photo}" if self.before_photo else None,
            "after_photo_url": f"/missions/evidence/{self.after_photo}" if self.after_photo else None,
            "video_url": f"/missions/evidence/{self.video_path}" if self.video_path else None,
            "description": self.description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_accuracy": self.location_accuracy,
            "capture_timestamp": self.capture_timestamp.isoformat() if self.capture_timestamp else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "verification_status": self.verification_status,
            "rejection_reason": self.rejection_reason,
            "confidence_score": self.confidence_score,
            "evidence_relevance": self.evidence_relevance,
            "before_after_comparison": self.before_after_comparison,
            "detected_inconsistencies": self.detected_inconsistencies,
            "verification_explanation": self.verification_explanation,
            "ai_findings": self.ai_findings,
            "review_decision": self.review_decision,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "image_hash_before": self.image_hash_before,
            "image_hash_after": self.image_hash_after,
            "is_demo_verification": self.is_demo_verification,
            "admin_feedback": self.admin_feedback or (self.rejection_reason if self.review_decision and "manual" in self.review_decision else None),
            "xp_awarded": self.xp_awarded,
            "xp_awarded_amount": self.xp_awarded_amount,
        }

    def __repr__(self):
        return (
            f"<Submission {self.reference_id} user={self.user_id} "
            f"mission={self.mission_id} status={self.verification_status}>"
        )


class XPTransaction(db.Model):
    """
    Immutable audit log for all experience point (XP) awards and deductions.
    Prevents duplicate rewards via unique reference_id constraint.
    """

    __tablename__ = "xp_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # 'mission_verification', 'lesson_quiz', 'manual_award'
    source_id = db.Column(db.Integer, nullable=True)
    reference_id = db.Column(db.String(100), unique=True, index=True, nullable=False)  # e.g. 'XP-SUB-00042'
    description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("xp_transactions", cascade="all, delete-orphan", lazy="dynamic"),
    )

    def to_dict(self):
        """Serialize transaction record."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "reference_id": self.reference_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<XPTransaction {self.reference_id}: user={self.user_id} amount=+{self.amount}>"


class Badge(db.Model):
    """
    Achievement badges earned by users for environmental milestones.
    """

    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, index=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), default="🏅", nullable=False)
    category = db.Column(db.String(50), default="General", nullable=False)
    requirement_description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    user_badges = db.relationship(
        "UserBadge",
        backref="badge",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self):
        """Serialize badge metadata."""
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "requirement_description": self.requirement_description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Badge {self.slug}: {self.name}>"


class UserBadge(db.Model):
    """
    Association table tracking badges earned by users.
    Unique constraint on (user_id, badge_id) guarantees no duplicate awards.
    """

    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_id = db.Column(
        db.Integer,
        db.ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    awarded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
    )

    user = db.relationship(
        "User",
        backref=db.backref("user_badges", cascade="all, delete-orphan", lazy="dynamic"),
    )

    def to_dict(self):
        """Serialize awarded badge information."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "badge_id": self.badge_id,
            "badge": self.badge.to_dict() if self.badge else None,
            "awarded_at": self.awarded_at.isoformat() if self.awarded_at else None,
        }

    def __repr__(self):
        return f"<UserBadge user={self.user_id} badge={self.badge_id}>"


class UserStreak(db.Model):
    """
    Tracks daily consecutive activity streaks for members.
    Prevents duplicate increments within the same calendar day and handles resets.
    """

    __tablename__ = "user_streaks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    current_streak = db.Column(db.Integer, default=0, nullable=False)
    longest_streak = db.Column(db.Integer, default=0, nullable=False)
    last_activity_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("streak_record", uselist=False, cascade="all, delete-orphan"),
    )

    def to_dict(self):
        """Serialize streak details."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_activity_date": self.last_activity_date.isoformat() if self.last_activity_date else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<UserStreak user={self.user_id} current={self.current_streak} longest={self.longest_streak}>"
