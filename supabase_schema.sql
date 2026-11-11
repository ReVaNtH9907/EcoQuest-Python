-- ============================================================
-- EcoQuest — Production Supabase PostgreSQL Schema DDL
-- ============================================================
-- This script contains the complete relational schema for EcoQuest.
-- Note: When DATABASE_URL is configured in Vercel/Supabase, EcoQuest's
-- create_app() will also automatically create missing tables safely.
-- You can also execute this script directly in the Supabase SQL Editor.
-- ============================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    college VARCHAR(150) NOT NULL,
    profile_picture VARCHAR(255) DEFAULT 'default-avatar.svg',
    email_verified BOOLEAN DEFAULT FALSE NOT NULL,
    phone_verified BOOLEAN DEFAULT FALSE NOT NULL,
    total_xp INTEGER DEFAULT 0 NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- 2. OTP Verifications Table
CREATE TABLE IF NOT EXISTS otp_verifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code VARCHAR(6) NOT NULL,
    purpose VARCHAR(30) DEFAULT 'email_verification' NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    used BOOLEAN DEFAULT FALSE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_otp_verifications_user_id ON otp_verifications (user_id);

-- 3. Lesson Categories Table
CREATE TABLE IF NOT EXISTS lesson_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR(50) DEFAULT '🌿' NOT NULL,
    "order" INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lesson_categories_slug ON lesson_categories (slug);

-- 4. Lessons Table
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES lesson_categories(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    summary TEXT NOT NULL,
    introduction TEXT NOT NULL,
    estimated_minutes INTEGER DEFAULT 5 NOT NULL,
    xp_reward INTEGER DEFAULT 50 NOT NULL,
    "order" INTEGER DEFAULT 0 NOT NULL,
    icon VARCHAR(50) DEFAULT '🌱' NOT NULL,
    content_sections JSONB NOT NULL,
    important_facts JSONB NOT NULL,
    key_takeaways JSONB NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lessons_category_id ON lessons (category_id);
CREATE INDEX IF NOT EXISTS ix_lessons_slug ON lessons (slug);

-- 5. Quiz Questions Table
CREATE TABLE IF NOT EXISTS quiz_questions (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    explanation TEXT NOT NULL,
    "order" INTEGER DEFAULT 0 NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_quiz_questions_lesson_id ON quiz_questions (lesson_id);

-- 6. Quiz Options Table
CREATE TABLE IF NOT EXISTS quiz_options (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE NOT NULL,
    "order" INTEGER DEFAULT 0 NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_quiz_options_question_id ON quiz_options (question_id);

-- 7. Lesson Progress Table
CREATE TABLE IF NOT EXISTS lesson_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    status VARCHAR(30) DEFAULT 'not_started' NOT NULL,
    completed BOOLEAN DEFAULT FALSE NOT NULL,
    xp_awarded BOOLEAN DEFAULT FALSE NOT NULL,
    highest_score DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    last_attempt_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    CONSTRAINT uq_user_lesson_progress UNIQUE (user_id, lesson_id)
);

CREATE INDEX IF NOT EXISTS ix_lesson_progress_user_id ON lesson_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_lesson_progress_lesson_id ON lesson_progress (lesson_id);

-- 8. Quiz Attempts Table
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    score DOUBLE PRECISION NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    passed BOOLEAN DEFAULT FALSE NOT NULL,
    user_answers JSONB,
    attempted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_quiz_attempts_user_id ON quiz_attempts (user_id);
CREATE INDEX IF NOT EXISTS ix_quiz_attempts_lesson_id ON quiz_attempts (lesson_id);

-- 9. Missions Table
CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    short_description VARCHAR(350) NOT NULL,
    category VARCHAR(50) NOT NULL,
    category_slug VARCHAR(50) NOT NULL,
    difficulty VARCHAR(30) NOT NULL,
    duration VARCHAR(50) NOT NULL,
    xp_reward INTEGER DEFAULT 150 NOT NULL,
    location VARCHAR(200) NOT NULL,
    why_it_matters TEXT NOT NULL,
    instructions JSONB NOT NULL,
    proof_requirements TEXT NOT NULL,
    safety_guidelines JSONB NOT NULL,
    image VARCHAR(255) DEFAULT 'mission-cleanup.svg' NOT NULL,
    icon VARCHAR(50) DEFAULT '🌱' NOT NULL,
    allow_repeat BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_missions_slug ON missions (slug);
CREATE INDEX IF NOT EXISTS ix_missions_category ON missions (category);
CREATE INDEX IF NOT EXISTS ix_missions_category_slug ON missions (category_slug);

-- 10. User Missions Table
CREATE TABLE IF NOT EXISTS user_missions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mission_id INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    status VARCHAR(30) DEFAULT 'accepted' NOT NULL,
    accepted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    completed_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_missions_user_id ON user_missions (user_id);
CREATE INDEX IF NOT EXISTS ix_user_missions_mission_id ON user_missions (mission_id);

-- 11. Submissions Table
CREATE TABLE IF NOT EXISTS submissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mission_id INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    before_photo VARCHAR(255) NOT NULL,
    after_photo VARCHAR(255) NOT NULL,
    video_path VARCHAR(255),
    description TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_accuracy DOUBLE PRECISION,
    capture_timestamp TIMESTAMP WITHOUT TIME ZONE,
    submitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    verification_status VARCHAR(40) DEFAULT 'Pending' NOT NULL,
    rejection_reason TEXT,
    confidence_score DOUBLE PRECISION,
    evidence_relevance VARCHAR(50),
    before_after_comparison TEXT,
    detected_inconsistencies TEXT,
    verification_explanation TEXT,
    ai_findings TEXT,
    review_decision VARCHAR(50),
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    image_hash_before VARCHAR(64),
    image_hash_after VARCHAR(64),
    is_demo_verification BOOLEAN DEFAULT FALSE NOT NULL,
    admin_feedback TEXT,
    xp_awarded BOOLEAN DEFAULT FALSE NOT NULL,
    xp_awarded_amount INTEGER DEFAULT 0 NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_submissions_user_id ON submissions (user_id);
CREATE INDEX IF NOT EXISTS ix_submissions_mission_id ON submissions (mission_id);
CREATE INDEX IF NOT EXISTS ix_submissions_verification_status ON submissions (verification_status);
CREATE INDEX IF NOT EXISTS ix_submissions_image_hash_before ON submissions (image_hash_before);
CREATE INDEX IF NOT EXISTS ix_submissions_image_hash_after ON submissions (image_hash_after);

-- 12. XP Transactions Table
CREATE TABLE IF NOT EXISTS xp_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_id INTEGER,
    reference_id VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_xp_transactions_user_id ON xp_transactions (user_id);
CREATE INDEX IF NOT EXISTS ix_xp_transactions_reference_id ON xp_transactions (reference_id);

-- 13. Badges Table
CREATE TABLE IF NOT EXISTS badges (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR(50) DEFAULT '🏅' NOT NULL,
    category VARCHAR(50) DEFAULT 'General' NOT NULL,
    requirement_description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_badges_slug ON badges (slug);

-- 14. User Badges Table
CREATE TABLE IF NOT EXISTS user_badges (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_id INTEGER NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    awarded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    CONSTRAINT uq_user_badge UNIQUE (user_id, badge_id)
);

CREATE INDEX IF NOT EXISTS ix_user_badges_user_id ON user_badges (user_id);
CREATE INDEX IF NOT EXISTS ix_user_badges_badge_id ON user_badges (badge_id);

-- 15. User Streaks Table
CREATE TABLE IF NOT EXISTS user_streaks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_streak INTEGER DEFAULT 0 NOT NULL,
    longest_streak INTEGER DEFAULT 0 NOT NULL,
    last_activity_date DATE,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_streaks_user_id ON user_streaks (user_id);

-- ============================================================
-- Supabase Storage Buckets Setup (Run in Supabase Dashboard):
-- 1. Create a Public Bucket: 'profile-pictures' (for public avatar images)
-- 2. Create a Private Bucket: 'mission-evidence' (for mission proof photos & videos)
-- ============================================================
