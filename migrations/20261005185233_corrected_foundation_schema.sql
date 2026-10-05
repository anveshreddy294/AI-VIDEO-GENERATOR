-- VisualAI corrected foundation; local review artifact, NOT applied.
-- Standalone replacement deployment for fresh project hqszkkvuxwdedhegqbec.
-- Historical migrations/001_supabase_initial_schema.sql MUST NOT run first.
-- CLI unavailable: filename uses the UTC timestamp convention.
-- Domain IDs remain text; security identity is exclusively auth.users.id UUID.
-- source_version on scoped child rows is the numeric source_versions.version;
-- source_versions.source_version retains the existing text label such as v1.
-- Deferred NO ACTION protects historical references at COMMIT while allowing
-- an explicit owner/source aggregate cascade. RESTRICT would prevent that cascade.
-- JSONB evidence/ID arrays remain validated application payloads: the trusted
-- backend must validate every embedded ID against this owner/source/version.
-- Bounds below encode CURRENT model contracts (scores, option indexes, bbox);
-- educational thresholds/durations remain application configuration.
BEGIN;

DO $preflight$
DECLARE
    conflicting text;
BEGIN
    IF to_regclass('auth.users') IS NULL THEN
        RAISE EXCEPTION 'Supabase auth.users is required';
    END IF;
    SELECT string_agg(name, ', ' ORDER BY name) INTO conflicting
    FROM unnest(ARRAY['profiles', 'sources', 'source_versions', 'content_units', 'concepts', 'concept_relationships', 'assessment_sessions', 'assessment_questions', 'assessment_attempts', 'concept_mastery', 'misconceptions', 'generated_videos', 'remediation_jobs', 'learning_profiles', 'video_target_matrices']) AS expected(name)
    WHERE to_regclass('public.' || name) IS NOT NULL;
    IF conflicting IS NOT NULL THEN
        RAISE EXCEPTION 'Fresh foundation required; conflicting objects: %', conflicting;
    END IF;
    IF to_regprocedure('public.visualai_set_updated_at()') IS NOT NULL THEN
        RAISE EXCEPTION 'Conflicting visualai_set_updated_at function';
    END IF;
END;
$preflight$;

CREATE TABLE public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name text,
    role text NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'instructor', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.sources (
    source_id text PRIMARY KEY CHECK (source_id <> ''),
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    legacy_student_id text,
    asset_id text NOT NULL,
    upload_id text NOT NULL,
    filename text NOT NULL,
    source_type text NOT NULL CHECK (source_type IN ('pdf', 'txt', 'image', 'video')),
    mime_type text NOT NULL,
    file_hash text NOT NULL,
    file_size bigint NOT NULL CHECK (file_size >= 0),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    source_version text NOT NULL DEFAULT 'v1',
    title text,
    sha256 text,
    parser_version text NOT NULL DEFAULT 'v1',
    sanitization_version text NOT NULL DEFAULT 'v1',
    parent_source_id text,
    status text NOT NULL DEFAULT 'UPLOADED' CHECK (status IN ('UPLOADED', 'PROCESSING', 'EXTRACTING', 'NORMALIZING', 'INDEXING', 'READY', 'FAILED', 'VISION_EXTRACTION_FAILED')),
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id),
    FOREIGN KEY (user_id, parent_source_id) REFERENCES public.sources(user_id, source_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CHECK (parent_source_id IS NULL OR parent_source_id <> source_id)
);

CREATE TABLE public.source_versions (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    source_version text NOT NULL,
    file_hash text NOT NULL,
    sha256 text,
    filename text NOT NULL,
    file_location text NOT NULL CHECK (file_location <> ''),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provenance) = 'object'),
    normalized_content jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(normalized_content) = 'array'),
    sanitized_content jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(sanitized_content) = 'array'),
    quarantined_content jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(quarantined_content) = 'array'),
    rich_chunks jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rich_chunks) = 'array'),
    topic_blueprint jsonb CHECK (topic_blueprint IS NULL OR jsonb_typeof(topic_blueprint) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, version),
    UNIQUE (user_id, source_id, version),
    UNIQUE (user_id, source_id, version, source_version),
    UNIQUE (source_id, source_version),
    FOREIGN KEY (user_id, source_id) REFERENCES public.sources(user_id, source_id) ON DELETE CASCADE
);

CREATE TABLE public.content_units (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    content_id text NOT NULL,
    asset_id text NOT NULL,
    layer text NOT NULL DEFAULT 'A' CHECK (layer = 'A'),
    modality text NOT NULL CHECK (modality IN ('pdf', 'image', 'txt', 'video')),
    text text NOT NULL,
    visual_description text,
    page_number integer,
    page_start integer,
    page_end integer,
    slide_number integer,
    timestamp_start double precision,
    timestamp_end double precision,
    speaker text,
    heading_path text[] NOT NULL DEFAULT '{}',
    frame_id text,
    sequence_index integer NOT NULL DEFAULT 0 CHECK (sequence_index >= 0),
    chapter text,
    section text,
    parent_content_id text,
    char_start integer,
    char_end integer,
    line_start integer,
    line_end integer,
    bbox jsonb CHECK (bbox IS NULL OR (jsonb_typeof(bbox) = 'array' AND jsonb_array_length(bbox) = 4)),
    region_id text,
    image_id text,
    image_path text,
    extraction_method text NOT NULL DEFAULT 'direct',
    confidence_score double precision NOT NULL DEFAULT 1.0 CHECK (confidence_score BETWEEN 0 AND 1),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provenance) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, source_version, content_id),
    UNIQUE (user_id, source_id, source_version, content_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, parent_content_id) REFERENCES public.content_units(user_id, source_id, source_version, content_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CHECK (parent_content_id IS NULL OR parent_content_id <> content_id),
    CHECK (timestamp_start IS NULL OR timestamp_start >= 0),
    CHECK (timestamp_end IS NULL OR timestamp_start IS NULL OR timestamp_end >= timestamp_start)
);

CREATE TABLE public.concepts (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    concept_id text NOT NULL,
    name text NOT NULL,
    definition text,
    source_content_ids text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, source_version, concept_id),
    UNIQUE (user_id, source_id, source_version, concept_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE
);

CREATE TABLE public.concept_relationships (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    concept_id text NOT NULL,
    related_concept_id text NOT NULL,
    relationship_type text NOT NULL CHECK (relationship_type IN ('prerequisite', 'related')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, source_version, concept_id, related_concept_id, relationship_type),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, related_concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE,
    CHECK (concept_id <> related_concept_id)
);

CREATE TABLE public.assessment_sessions (
    session_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    legacy_student_id text,
    status text NOT NULL DEFAULT 'PLANNING' CHECK (status IN ('PLANNING', 'GENERATING', 'VALIDATING', 'READY', 'SUBMITTED', 'EXPIRED', 'FAILED')),
    concept_queue text[] NOT NULL DEFAULT '{}',
    current_index integer NOT NULL DEFAULT 0 CHECK (current_index >= 0),
    concept_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(concept_snapshot) = 'object'),
    submission_response jsonb CHECK (submission_response IS NULL OR jsonb_typeof(submission_response) = 'object'),
    submitted_answers jsonb CHECK (submitted_answers IS NULL OR jsonb_typeof(submitted_answers) = 'object'),
    expires_at timestamptz,
    submitted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id, source_version, session_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE
);

CREATE TABLE public.assessment_questions (
    question_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    session_id text,
    concept_id text NOT NULL,
    concept_name text NOT NULL DEFAULT '',
    stem text NOT NULL,
    options jsonb NOT NULL CHECK (jsonb_typeof(options) = 'array' AND jsonb_array_length(options) > 0),
    correct_index integer NOT NULL CHECK (correct_index >= 0),
    explanation text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ANSWERED')),
    difficulty text NOT NULL DEFAULT 'intermediate' CHECK (difficulty IN ('foundational', 'intermediate', 'advanced')),
    distractor_misconceptions jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(distractor_misconceptions) = 'object'),
    evidence_quote text NOT NULL DEFAULT '',
    evidence_text text NOT NULL DEFAULT '',
    chunk_ids text[] NOT NULL DEFAULT '{}',
    content_ids text[] NOT NULL DEFAULT '{}',
    page_start integer,
    page_end integer,
    timestamp_start text,
    timestamp_end text,
    variant_type text,
    diagnostics jsonb CHECK (diagnostics IS NULL OR jsonb_typeof(diagnostics) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id, source_version, concept_id, question_id),
    UNIQUE (user_id, source_id, source_version, session_id, concept_id, question_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CHECK (correct_index < jsonb_array_length(options))
);

CREATE TABLE public.assessment_attempts (
    attempt_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    session_id text,
    concept_id text NOT NULL,
    question_id text NOT NULL,
    assessment_type text NOT NULL CHECK (assessment_type IN ('DIAGNOSTIC', 'REASSESSMENT')),
    selected_answer integer NOT NULL CHECK (selected_answer BETWEEN 0 AND 10),
    correct_answer integer NOT NULL CHECK (correct_answer BETWEEN 0 AND 10),
    is_correct boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id, source_version, attempt_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, concept_id, question_id) REFERENCES public.assessment_questions(user_id, source_id, source_version, concept_id, question_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id, concept_id, question_id) REFERENCES public.assessment_questions(user_id, source_id, source_version, session_id, concept_id, question_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CHECK (is_correct = (selected_answer = correct_answer))
);

CREATE TABLE public.concept_mastery (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    concept_id text NOT NULL,
    session_id text,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    correct_count integer NOT NULL DEFAULT 0 CHECK (correct_count >= 0),
    incorrect_count integer NOT NULL DEFAULT 0 CHECK (incorrect_count >= 0),
    reassessment_attempt_count integer NOT NULL DEFAULT 0 CHECK (reassessment_attempt_count >= 0),
    reassessment_correct_count integer NOT NULL DEFAULT 0 CHECK (reassessment_correct_count >= 0),
    lifetime_accuracy double precision NOT NULL DEFAULT 0 CHECK (lifetime_accuracy BETWEEN 0 AND 100),
    mastery_score double precision NOT NULL DEFAULT 0 CHECK (mastery_score BETWEEN 0 AND 100),
    mastery_state text NOT NULL DEFAULT 'UNASSESSED' CHECK (mastery_state IN ('UNASSESSED', 'LEARNING', 'WEAK', 'REMEDIATING', 'REASSESSING', 'MASTERED', 'NEEDS_SUPPORT')),
    remediation_attempt_count integer NOT NULL DEFAULT 0 CHECK (remediation_attempt_count >= 0),
    processed_attempt_ids text[] NOT NULL DEFAULT '{}',
    last_assessed_at timestamptz,
    last_remediation_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, source_id, source_version, concept_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CHECK (correct_count + incorrect_count = attempt_count),
    CHECK (reassessment_correct_count <= reassessment_attempt_count),
    CHECK (reassessment_attempt_count <= attempt_count)
);

CREATE TABLE public.misconceptions (
    misconception_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    session_id text,
    concept_id text NOT NULL,
    misconception_code text NOT NULL,
    misconception_label text NOT NULL DEFAULT '',
    misconception_description text NOT NULL DEFAULT '',
    misconception_type text NOT NULL DEFAULT 'general',
    evidence_question_ids text[] NOT NULL DEFAULT '{}',
    evidence_attempt_ids text[] NOT NULL DEFAULT '{}',
    occurrence_count integer NOT NULL DEFAULT 1 CHECK (occurrence_count >= 1),
    confidence_state text NOT NULL DEFAULT 'POSSIBLE' CHECK (confidence_state IN ('POSSIBLE', 'LIKELY', 'CONFIRMED')),
    status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CORRECTED', 'RECURRENT')),
    first_detected_at timestamptz NOT NULL DEFAULT now(),
    last_detected_at timestamptz NOT NULL DEFAULT now(),
    corrected_at timestamptz,
    source_chunk_ids text[] NOT NULL DEFAULT '{}',
    supporting_evidence_summary text,
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE public.generated_videos (
    job_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    legacy_student_id text,
    concept_id text NOT NULL,
    concept_name text NOT NULL DEFAULT '',
    duration_seconds double precision NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    status text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'PLANNING', 'RENDERING', 'GENERATING_AUDIO', 'ALIGNING', 'COMPOSITING', 'COMPLETED', 'FAILED')),
    stage text NOT NULL DEFAULT 'QUEUED',
    progress integer NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    video_path text,
    audio_path text,
    subtitle_path text,
    provenance_chunks text[] NOT NULL DEFAULT '{}',
    source_content_ids text[] NOT NULL DEFAULT '{}',
    page_start integer,
    page_end integer,
    plan jsonb CHECK (plan IS NULL OR jsonb_typeof(plan) = 'object'),
    output_metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(output_metadata) = 'object'),
    error text,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id, source_version, concept_id, job_id),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE public.remediation_jobs (
    remediation_job_id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    session_id text,
    concept_id text NOT NULL,
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'READY', 'FAILED')),
    video_job_id text,
    video_path text,
    duration_seconds double precision CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    attempt_number integer NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
    idempotency_key text NOT NULL,
    strategy_used text,
    misconception_code text,
    evidence_attempt_ids text[] NOT NULL DEFAULT '{}',
    started_at timestamptz,
    completed_at timestamptz,
    failed_at timestamptz,
    failure_code text,
    failure_message text,
    is_infrastructure_failure boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, source_id, source_version, idempotency_key),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (user_id, source_id, source_version, concept_id, video_job_id) REFERENCES public.generated_videos(user_id, source_id, source_version, concept_id, job_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE public.learning_profiles (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    legacy_student_id text,
    overall_score double precision NOT NULL DEFAULT 0 CHECK (overall_score BETWEEN 0 AND 100),
    total_sessions integer NOT NULL DEFAULT 0 CHECK (total_sessions >= 0),
    strong_concepts text[] NOT NULL DEFAULT '{}',
    weak_concepts text[] NOT NULL DEFAULT '{}',
    strong_concept_ids text[] NOT NULL DEFAULT '{}',
    weak_concept_ids text[] NOT NULL DEFAULT '{}',
    prerequisite_gaps text[] NOT NULL DEFAULT '{}',
    concept_masteries jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(concept_masteries) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, source_id, source_version),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE
);

CREATE TABLE public.video_target_matrices (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    session_id text,
    legacy_student_id text,
    schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    generated_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, source_id, source_version),
    FOREIGN KEY (user_id, source_id, source_version) REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES public.assessment_sessions(user_id, source_id, source_version, session_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
);

-- Current source/version pointer is checked after both tables exist.
ALTER TABLE public.sources ADD CONSTRAINT sources_current_version_fk
    FOREIGN KEY (user_id, source_id, version, source_version)
    REFERENCES public.source_versions(user_id, source_id, version, source_version)
    ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- Updates use the database clock; this invoker trigger has no elevated privileges.
CREATE FUNCTION public.visualai_set_updated_at() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $function$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$function$;
REVOKE ALL ON FUNCTION public.visualai_set_updated_at() FROM PUBLIC, anon, authenticated;

CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER sources_set_updated_at BEFORE UPDATE ON public.sources
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER assessment_sessions_set_updated_at BEFORE UPDATE ON public.assessment_sessions
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER assessment_questions_set_updated_at BEFORE UPDATE ON public.assessment_questions
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER concept_mastery_set_updated_at BEFORE UPDATE ON public.concept_mastery
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER generated_videos_set_updated_at BEFORE UPDATE ON public.generated_videos
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER remediation_jobs_set_updated_at BEFORE UPDATE ON public.remediation_jobs
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER learning_profiles_set_updated_at BEFORE UPDATE ON public.learning_profiles
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();
CREATE TRIGGER video_target_matrices_set_updated_at BEFORE UPDATE ON public.video_target_matrices
    FOR EACH ROW EXECUTE FUNCTION public.visualai_set_updated_at();

CREATE INDEX sources_lookup_1_idx ON public.sources (user_id, file_hash);
CREATE INDEX sources_lookup_2_idx ON public.sources (user_id, status);
CREATE INDEX sources_lookup_3_idx ON public.sources (user_id, parent_source_id);
CREATE INDEX source_versions_lookup_1_idx ON public.source_versions (user_id, source_id, version);
CREATE INDEX content_units_lookup_1_idx ON public.content_units (user_id, source_id, source_version, sequence_index);
CREATE INDEX content_units_lookup_2_idx ON public.content_units (user_id, source_id, source_version, parent_content_id);
CREATE INDEX concepts_lookup_1_idx ON public.concepts (user_id, source_id, source_version);
CREATE INDEX concept_relationships_lookup_1_idx ON public.concept_relationships (user_id, source_id, source_version, concept_id);
CREATE INDEX concept_relationships_lookup_2_idx ON public.concept_relationships (user_id, source_id, source_version, related_concept_id);
CREATE INDEX assessment_sessions_lookup_1_idx ON public.assessment_sessions (user_id, source_id, source_version, status);
CREATE INDEX assessment_questions_lookup_1_idx ON public.assessment_questions (user_id, source_id, source_version, session_id);
CREATE INDEX assessment_questions_lookup_2_idx ON public.assessment_questions (user_id, source_id, source_version, concept_id);
CREATE INDEX assessment_attempts_lookup_1_idx ON public.assessment_attempts (user_id, source_id, source_version, concept_id, submitted_at);
CREATE INDEX assessment_attempts_lookup_2_idx ON public.assessment_attempts (user_id, source_id, source_version, session_id);
CREATE INDEX assessment_attempts_lookup_3_idx ON public.assessment_attempts (user_id, source_id, source_version, concept_id, question_id);
CREATE INDEX concept_mastery_lookup_1_idx ON public.concept_mastery (user_id, source_id, source_version, session_id);
CREATE INDEX concept_mastery_lookup_2_idx ON public.concept_mastery (user_id, mastery_state);
CREATE INDEX misconceptions_lookup_1_idx ON public.misconceptions (user_id, source_id, source_version, concept_id, status);
CREATE INDEX misconceptions_lookup_2_idx ON public.misconceptions (user_id, source_id, source_version, session_id);
CREATE INDEX generated_videos_lookup_1_idx ON public.generated_videos (user_id, source_id, source_version, concept_id);
CREATE INDEX generated_videos_lookup_2_idx ON public.generated_videos (user_id, status);
CREATE INDEX remediation_jobs_lookup_1_idx ON public.remediation_jobs (user_id, source_id, source_version, concept_id, status);
CREATE INDEX remediation_jobs_lookup_2_idx ON public.remediation_jobs (user_id, source_id, source_version, session_id);
CREATE INDEX remediation_jobs_lookup_3_idx ON public.remediation_jobs (user_id, source_id, source_version, concept_id, video_job_id);
CREATE INDEX learning_profiles_lookup_1_idx ON public.learning_profiles (user_id, source_id, source_version);
CREATE INDEX video_target_matrices_lookup_1_idx ON public.video_target_matrices (user_id, source_id, source_version, session_id);

-- All application rows are private. Default grants may have been inherited,
-- so explicitly remove PUBLIC/anon/authenticated privileges on these NEW tables.
-- service_role writes are trusted backend only; never send its key to clients.
-- Owner SELECT policies on hidden tables are defense in depth only: no learner
-- grants below make their answer keys/snapshots accessible through PostgREST.
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.profiles FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.profiles TO service_role;
CREATE POLICY profiles_owner_select ON public.profiles
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = id);

ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.sources FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.sources TO service_role;
CREATE POLICY sources_owner_select ON public.sources
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.source_versions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.source_versions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.source_versions TO service_role;
CREATE POLICY source_versions_owner_select ON public.source_versions
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.content_units ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.content_units FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.content_units TO service_role;
CREATE POLICY content_units_owner_select ON public.content_units
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.concepts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.concepts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.concepts TO service_role;
CREATE POLICY concepts_owner_select ON public.concepts
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.concept_relationships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.concept_relationships FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.concept_relationships TO service_role;
CREATE POLICY concept_relationships_owner_select ON public.concept_relationships
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.assessment_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.assessment_sessions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.assessment_sessions TO service_role;
CREATE POLICY assessment_sessions_owner_select ON public.assessment_sessions
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.assessment_questions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.assessment_questions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.assessment_questions TO service_role;
CREATE POLICY assessment_questions_owner_select ON public.assessment_questions
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.assessment_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.assessment_attempts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.assessment_attempts TO service_role;
CREATE POLICY assessment_attempts_owner_select ON public.assessment_attempts
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.concept_mastery ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.concept_mastery FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.concept_mastery TO service_role;
CREATE POLICY concept_mastery_owner_select ON public.concept_mastery
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.misconceptions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.misconceptions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.misconceptions TO service_role;
CREATE POLICY misconceptions_owner_select ON public.misconceptions
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.generated_videos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.generated_videos FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.generated_videos TO service_role;
CREATE POLICY generated_videos_owner_select ON public.generated_videos
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.remediation_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.remediation_jobs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.remediation_jobs TO service_role;
CREATE POLICY remediation_jobs_owner_select ON public.remediation_jobs
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.learning_profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.learning_profiles FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.learning_profiles TO service_role;
CREATE POLICY learning_profiles_owner_select ON public.learning_profiles
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

ALTER TABLE public.video_target_matrices ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.video_target_matrices FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.video_target_matrices TO service_role;
CREATE POLICY video_target_matrices_owner_select ON public.video_target_matrices
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

GRANT SELECT ON TABLE public.profiles, public.sources, public.source_versions, public.content_units, public.concepts, public.concept_relationships, public.concept_mastery, public.misconceptions, public.generated_videos, public.remediation_jobs, public.learning_profiles TO authenticated;

-- Profile creation/update can modify display identity only, never privileged role.
GRANT INSERT (id, full_name), UPDATE (full_name) ON public.profiles TO authenticated;
CREATE POLICY profiles_owner_insert ON public.profiles
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = id);
CREATE POLICY profiles_owner_update ON public.profiles
    FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = id)
    WITH CHECK ((SELECT auth.uid()) = id);

-- All other INSERT/UPDATE/DELETE operations intentionally have no authenticated
-- grants or policies: source lifecycle, grades, mastery and jobs are server-owned.
-- No direct learner DELETE: aggregate deletion is a verified backend operation.
--
-- Safe assessment access contract (implemented in a LATER application slice):
-- verify the Supabase JWT, derive user_id from verified sub, authorize source
-- ownership, and serialize SafeQuestion/SafeOption allowlists through the API.
-- Never return correct_index, explanation, evidence_text, distractor metadata,
-- answer-bearing options, snapshots, grading state or raw matrix payloads before
-- the authorized release point. Do not use SELECT * or a definer view.
-- Backend bypass of RLS REQUIRES explicit owner filtering and immutable user_id.
-- Metadata legacy_student_id, uploaded_by/owner_user_id compatibility aliases
-- MUST NOT authorize access; map identity aliases from verified user_id.
-- Version labels map to numeric source_version through source_versions.
-- Canonical ingest writes source + version + content atomically, then indexes
-- Qdrant. No Supabase-error-to-local-JSON success path is permitted.
--
-- Nested payload validation and embedded evidence integrity stay in the backend;
-- scalar references above enforce UUID owner, source, version and concept scope.
-- Model mapping contract:
-- SourceRecord uploaded_by/owner_user_id map to UUID user_id; no student default.
-- ConceptNode prerequisite_concept_ids/related_concept_ids map to scoped edges.
-- AssessmentSession.questions normalize into assessment_questions; snapshots
-- retain their existing JSON shape and session timestamps may be nullable.
-- Question and AuthoritativeQuestion share stem/answer/provenance storage;
-- serialize structured diagnostic options and reassessment string options
-- through separate model-aware adapters, never through a blind model_validate.
-- Step 2 ConceptMastery lives inside learning_profiles.concept_masteries;
-- Step 5 MasteryRecord lives in concept_mastery with its own exact state machine.
-- VideoArtifact.student_id and StudentLearningProfile.student_id map to
-- legacy_student_id; VideoPlan is preserved in generated_videos.plan.
-- VideoTargetMatrix is preserved losslessly in payload (including generated_at
-- and schema_version); scalar mirror columns must agree with validated payload.
-- PostgreSQL text timestamp_start/end on questions preserve their CURRENT
-- float|string union; the adapter must restore validated model representations.
COMMIT;

