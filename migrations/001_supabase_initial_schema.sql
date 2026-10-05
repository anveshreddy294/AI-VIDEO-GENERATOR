-- ==============================================================================
-- VisualAI — Canonical Supabase Relational Schema (Migration 001)
-- Domain entities for Steps 1 through 5:
-- Ingestion + Knowledge Graph + Assessment + Video Engine + Adaptive Learning
-- ==============================================================================

-- 1. PROFILES (Extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY,
    email TEXT,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'instructor', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. SOURCES (Step 1 Ingestion Metadata)
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL DEFAULT 'student_default',
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    modality TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UPLOADED' CHECK (status IN ('UPLOADED', 'PROCESSING', 'EXTRACTING', 'NORMALIZING', 'INDEXING', 'READY', 'FAILED', 'VISION_EXTRACTION_FAILED')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id);
CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(file_hash);

-- 3. SOURCE VERSIONS
CREATE TABLE IF NOT EXISTS source_versions (
    version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    version_number INT NOT NULL DEFAULT 1,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. CONTENT UNITS (Normalized Step 1 Extract)
CREATE TABLE IF NOT EXISTS content_units (
    content_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL,
    user_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    modality TEXT NOT NULL,
    text TEXT NOT NULL,
    visual_description TEXT,
    page_number INT,
    sequence_index INT NOT NULL DEFAULT 0,
    chapter TEXT,
    section TEXT,
    bbox JSONB,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    extraction_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_content_units_source ON content_units(source_id);

-- 5. CONCEPTS (Knowledge Graph Nodes)
CREATE TABLE IF NOT EXISTS concepts (
    concept_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    definition TEXT,
    difficulty TEXT DEFAULT 'intermediate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_concepts_source ON concepts(source_id);

-- 6. CONCEPT RELATIONSHIPS (Knowledge Graph Prerequisite Edges)
CREATE TABLE IF NOT EXISTS concept_relationships (
    relationship_id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    prerequisite_concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'prerequisite',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_concept_edge UNIQUE (concept_id, prerequisite_concept_id)
);

-- 7. ASSESSMENT SESSIONS (Step 2 Assessment State)
CREATE TABLE IF NOT EXISTS assessment_sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    user_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'CREATED' CHECK (status IN ('CREATED', 'ACTIVE', 'SUBMITTED', 'EXPIRED')),
    submission_response JSONB,
    submitted_answers JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    expires_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sessions_student_source ON assessment_sessions(student_id, source_id);

-- 8. ASSESSMENT QUESTIONS (Step 2 Safe and Grounded Questions)
CREATE TABLE IF NOT EXISTS assessment_questions (
    question_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assessment_sessions(session_id) ON DELETE CASCADE,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    concept_name TEXT NOT NULL,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_index INT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_quote TEXT,
    difficulty TEXT DEFAULT 'medium',
    prerequisite_concept_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_questions_session ON assessment_questions(session_id);

-- 9. ASSESSMENT ATTEMPTS (Step 2 & 5 Attempt History)
CREATE TABLE IF NOT EXISTS assessment_attempts (
    attempt_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    session_id TEXT REFERENCES assessment_sessions(session_id) ON DELETE SET NULL,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    selected_answer INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    assessment_type TEXT NOT NULL DEFAULT 'DIAGNOSTIC',
    latency_ms INT DEFAULT 0,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_attempts_user_concept ON assessment_attempts(user_id, concept_id);

-- 10. CONCEPT MASTERY (Step 2 & 5 Student Knowledge Profile)
CREATE TABLE IF NOT EXISTS concept_mastery (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    concept_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN ('NOT_STARTED', 'IN_PROGRESS', 'NEEDS_REMEDIATION', 'MASTERED', 'REQUIRES_HUMAN_FALLBACK')),
    attempts_count INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    consecutive_successes INT NOT NULL DEFAULT 0,
    consecutive_failures INT NOT NULL DEFAULT 0,
    last_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_user_concept UNIQUE (user_id, concept_id)
);
CREATE INDEX IF NOT EXISTS idx_mastery_user ON concept_mastery(user_id);

-- 11. MISCONCEPTIONS (Step 5 Intelligent Error Classification)
CREATE TABLE IF NOT EXISTS misconceptions (
    misconception_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    error_category TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.8,
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    remediation_priority INT NOT NULL DEFAULT 1,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    resolved_at TIMESTAMPTZ
);

-- 12. REMEDIATION JOBS (Step 5 Personalized Recovery Flow)
CREATE TABLE IF NOT EXISTS remediation_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'GENERATING_VIDEO', 'COMPLETED', 'FAILED')),
    strategy TEXT NOT NULL,
    video_plan JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    completed_at TIMESTAMPTZ
);

-- 13. GENERATED VIDEOS (Step 3 Video Engine Output)
CREATE TABLE IF NOT EXISTS generated_videos (
    video_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    concept_id TEXT REFERENCES concepts(concept_id) ON DELETE SET NULL,
    render_path TEXT NOT NULL,
    audio_path TEXT,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE concept_mastery ENABLE ROW LEVEL SECURITY;
ALTER TABLE misconceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_videos ENABLE ROW LEVEL SECURITY;

-- Allow users access to their own data when Supabase Auth is active
CREATE POLICY "Users can view their own profile" ON profiles
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can access their own sources" ON sources
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can access their own content units" ON content_units
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can access their own assessment sessions" ON assessment_sessions
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);
