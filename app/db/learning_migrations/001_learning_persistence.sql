-- Frozen structural snapshot of the deployed canonical contracts, 2026-10-11.
-- Contains no user rows or credentials. Separate private schemas; no remote DDL.
-- Supabase Auth verifies the caller before the backend sets visualai.owner_id.
CREATE SCHEMA visualai_learning;
CREATE SCHEMA visualai_learning_private;
REVOKE ALL ON SCHEMA visualai_learning, visualai_learning_private FROM PUBLIC;
CREATE FUNCTION visualai_learning_private.owner_id() RETURNS uuid LANGUAGE sql STABLE
SET search_path='' AS $$ SELECT nullif(current_setting('visualai.owner_id',true),'')::uuid $$;
REVOKE ALL ON FUNCTION visualai_learning_private.owner_id() FROM PUBLIC;

CREATE TABLE visualai_learning.assessment_attempts (
    attempt_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    session_id text,
    concept_id text NOT NULL,
    question_id text NOT NULL,
    assessment_type text NOT NULL,
    selected_answer integer NOT NULL,
    correct_answer integer NOT NULL,
    is_correct boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE visualai_learning.assessment_questions (
    question_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    session_id text,
    concept_id text NOT NULL,
    concept_name text DEFAULT ''::text NOT NULL,
    stem text NOT NULL,
    options jsonb NOT NULL,
    correct_index integer NOT NULL,
    explanation text DEFAULT ''::text NOT NULL,
    status text DEFAULT 'PENDING'::text NOT NULL,
    difficulty text DEFAULT 'intermediate'::text NOT NULL,
    distractor_misconceptions jsonb DEFAULT '{}'::jsonb NOT NULL,
    evidence_quote text DEFAULT ''::text NOT NULL,
    evidence_text text DEFAULT ''::text NOT NULL,
    chunk_ids text[] DEFAULT '{}'::text[] NOT NULL,
    content_ids text[] DEFAULT '{}'::text[] NOT NULL,
    page_start integer,
    page_end integer,
    timestamp_start text,
    timestamp_end text,
    variant_type text,
    diagnostics jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    evidence_ids text[] DEFAULT '{}'::text[] NOT NULL
);

CREATE TABLE visualai_learning.assessment_sessions (
    session_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    legacy_student_id text,
    status text DEFAULT 'PLANNING'::text NOT NULL,
    concept_queue text[] DEFAULT '{}'::text[] NOT NULL,
    current_index integer DEFAULT 0 NOT NULL,
    concept_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    submission_response jsonb,
    submitted_answers jsonb,
    expires_at timestamp with time zone,
    submitted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    learning_session_id uuid,
    request_hash text,
    mastery_applied_at timestamp with time zone,
    assessment_type text DEFAULT 'DIAGNOSTIC'::text NOT NULL,
    reassessment_job_id text
);

CREATE TABLE visualai_learning.concept_mastery (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    concept_id text NOT NULL,
    session_id text,
    attempt_count integer DEFAULT 0 NOT NULL,
    correct_count integer DEFAULT 0 NOT NULL,
    incorrect_count integer DEFAULT 0 NOT NULL,
    reassessment_attempt_count integer DEFAULT 0 NOT NULL,
    reassessment_correct_count integer DEFAULT 0 NOT NULL,
    lifetime_accuracy double precision DEFAULT 0 NOT NULL,
    mastery_score double precision DEFAULT 0 NOT NULL,
    mastery_state text DEFAULT 'UNASSESSED'::text NOT NULL,
    remediation_attempt_count integer DEFAULT 0 NOT NULL,
    processed_attempt_ids text[] DEFAULT '{}'::text[] NOT NULL,
    last_assessed_at timestamp with time zone,
    last_remediation_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    mastery_id uuid DEFAULT gen_random_uuid() NOT NULL,
    consecutive_correct integer DEFAULT 0 NOT NULL,
    learning_session_id uuid
);

CREATE TABLE visualai_learning.concept_relationships (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    concept_id text NOT NULL,
    related_concept_id text NOT NULL,
    relationship_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    provenance jsonb DEFAULT '{}'::jsonb NOT NULL,
    evidence_content_ids text[] DEFAULT '{}'::text[] NOT NULL
);

CREATE TABLE visualai_learning.concepts (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    concept_id text NOT NULL,
    name text NOT NULL,
    definition text,
    source_content_ids text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    subtopic_id text,
    sequence integer,
    provenance jsonb DEFAULT '{}'::jsonb NOT NULL
);

CREATE TABLE visualai_learning.content_concepts (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    content_id text NOT NULL,
    concept_id text NOT NULL,
    support_kind text NOT NULL,
    char_start integer,
    char_end integer,
    extraction_confidence numeric,
    provenance jsonb NOT NULL
);

CREATE TABLE visualai_learning.content_units (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    content_id text NOT NULL,
    asset_id text NOT NULL,
    layer text DEFAULT 'A'::text NOT NULL,
    modality text NOT NULL,
    text text NOT NULL,
    visual_description text,
    page_number integer,
    page_start integer,
    page_end integer,
    slide_number integer,
    timestamp_start double precision,
    timestamp_end double precision,
    speaker text,
    heading_path text[] DEFAULT '{}'::text[] NOT NULL,
    frame_id text,
    sequence_index integer DEFAULT 0 NOT NULL,
    chapter text,
    section text,
    parent_content_id text,
    char_start integer,
    char_end integer,
    line_start integer,
    line_end integer,
    bbox jsonb,
    region_id text,
    image_id text,
    image_path text,
    extraction_method text DEFAULT 'direct'::text NOT NULL,
    confidence_score double precision DEFAULT 1.0 NOT NULL,
    provenance jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE visualai_learning.generated_videos (
    job_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    legacy_student_id text,
    concept_id text NOT NULL,
    concept_name text DEFAULT ''::text NOT NULL,
    duration_seconds double precision DEFAULT 0 NOT NULL,
    status text DEFAULT 'QUEUED'::text NOT NULL,
    stage text DEFAULT 'QUEUED'::text NOT NULL,
    progress integer DEFAULT 0 NOT NULL,
    video_path text,
    audio_path text,
    subtitle_path text,
    provenance_chunks text[] DEFAULT '{}'::text[] NOT NULL,
    source_content_ids text[] DEFAULT '{}'::text[] NOT NULL,
    page_start integer,
    page_end integer,
    plan jsonb,
    output_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error text,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE visualai_learning.learning_profiles (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    legacy_student_id text,
    overall_score double precision DEFAULT 0 NOT NULL,
    total_sessions integer DEFAULT 0 NOT NULL,
    strong_concepts text[] DEFAULT '{}'::text[] NOT NULL,
    weak_concepts text[] DEFAULT '{}'::text[] NOT NULL,
    strong_concept_ids text[] DEFAULT '{}'::text[] NOT NULL,
    weak_concept_ids text[] DEFAULT '{}'::text[] NOT NULL,
    prerequisite_gaps text[] DEFAULT '{}'::text[] NOT NULL,
    concept_masteries jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE visualai_learning.learning_sessions (
    session_id uuid NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    topic_id text NOT NULL,
    subtopic_id text,
    selected_concept_ids text[] NOT NULL,
    state text DEFAULT 'ACTIVE'::text NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    last_active_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    mastery_revision integer DEFAULT 0 NOT NULL
);

CREATE TABLE visualai_learning.misconceptions (
    misconception_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    session_id text,
    concept_id text NOT NULL,
    misconception_code text NOT NULL,
    misconception_label text DEFAULT ''::text NOT NULL,
    misconception_description text DEFAULT ''::text NOT NULL,
    misconception_type text DEFAULT 'general'::text NOT NULL,
    evidence_question_ids text[] DEFAULT '{}'::text[] NOT NULL,
    evidence_attempt_ids text[] DEFAULT '{}'::text[] NOT NULL,
    occurrence_count integer DEFAULT 1 NOT NULL,
    confidence_state text DEFAULT 'POSSIBLE'::text NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL,
    first_detected_at timestamp with time zone DEFAULT now() NOT NULL,
    last_detected_at timestamp with time zone DEFAULT now() NOT NULL,
    corrected_at timestamp with time zone,
    source_chunk_ids text[] DEFAULT '{}'::text[] NOT NULL,
    supporting_evidence_summary text,
    learning_session_id uuid
);

CREATE TABLE visualai_learning.profiles (
    id uuid NOT NULL,
    full_name text,
    role text DEFAULT 'student'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    learning_preferences jsonb DEFAULT '{}'::jsonb NOT NULL
);

CREATE TABLE visualai_learning.remediation_jobs (
    remediation_job_id text NOT NULL,
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    session_id text,
    concept_id text NOT NULL,
    status text DEFAULT 'PENDING'::text NOT NULL,
    video_job_id text,
    video_path text,
    duration_seconds double precision,
    attempt_number integer DEFAULT 1 NOT NULL,
    idempotency_key text NOT NULL,
    strategy_used text,
    misconception_code text,
    evidence_attempt_ids text[] DEFAULT '{}'::text[] NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    failed_at timestamp with time zone,
    failure_code text,
    failure_message text,
    is_infrastructure_failure boolean DEFAULT false NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    learning_session_id uuid
);

CREATE TABLE visualai_learning.source_versions (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    version integer NOT NULL,
    source_version text NOT NULL,
    file_hash text NOT NULL,
    sha256 text,
    filename text NOT NULL,
    file_location text NOT NULL,
    provenance jsonb DEFAULT '{}'::jsonb NOT NULL,
    normalized_content jsonb DEFAULT '[]'::jsonb NOT NULL,
    sanitized_content jsonb DEFAULT '[]'::jsonb NOT NULL,
    quarantined_content jsonb DEFAULT '[]'::jsonb NOT NULL,
    rich_chunks jsonb DEFAULT '[]'::jsonb NOT NULL,
    topic_blueprint jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    knowledge_state text DEFAULT 'LEGACY_UNMAPPED'::text NOT NULL,
    knowledge_schema_version integer,
    knowledge_operation_id uuid,
    knowledge_payload_hash text,
    knowledge_committed_at timestamp with time zone,
    knowledge_diagnostics jsonb DEFAULT '{}'::jsonb NOT NULL
);

CREATE TABLE visualai_learning.sources (
    source_id text NOT NULL,
    user_id uuid NOT NULL,
    legacy_student_id text,
    asset_id text NOT NULL,
    upload_id text NOT NULL,
    filename text NOT NULL,
    source_type text NOT NULL,
    mime_type text NOT NULL,
    file_hash text NOT NULL,
    file_size bigint NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    source_version text DEFAULT 'v1'::text NOT NULL,
    title text,
    sha256 text,
    parser_version text DEFAULT 'v1'::text NOT NULL,
    sanitization_version text DEFAULT 'v1'::text NOT NULL,
    parent_source_id text,
    status text DEFAULT 'UPLOADED'::text NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE visualai_learning.subtopics (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    subtopic_id text NOT NULL,
    topic_id text NOT NULL,
    title text NOT NULL,
    description text,
    sequence integer NOT NULL,
    provenance jsonb NOT NULL
);

CREATE TABLE visualai_learning.topics (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    topic_id text NOT NULL,
    title text NOT NULL,
    description text,
    sequence integer NOT NULL,
    provenance jsonb NOT NULL
);

CREATE TABLE visualai_learning.video_target_matrices (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    session_id text,
    legacy_student_id text,
    schema_version integer DEFAULT 1 NOT NULL,
    payload jsonb NOT NULL,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_assessment_type_check CHECK (assessment_type = ANY (ARRAY['DIAGNOSTIC'::text, 'REASSESSMENT'::text]));
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_check CHECK (is_correct = (selected_answer = correct_answer));
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_correct_answer_check CHECK (correct_answer >= 0 AND correct_answer <= 10);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_pkey PRIMARY KEY (attempt_id);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_selected_answer_check CHECK (selected_answer >= 0 AND selected_answer <= 10);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_attemp_key UNIQUE (user_id, source_id, source_version, attempt_id);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_check CHECK (correct_index < jsonb_array_length(options));
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_correct_index_check CHECK (correct_index >= 0);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_diagnostics_check CHECK (diagnostics IS NULL OR jsonb_typeof(diagnostics) = 'object'::text);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_difficulty_check CHECK (difficulty = ANY (ARRAY['foundational'::text, 'intermediate'::text, 'advanced'::text]));
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_distractor_misconceptions_check CHECK (jsonb_typeof(distractor_misconceptions) = 'object'::text);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_options_check CHECK (jsonb_typeof(options) = 'array'::text AND jsonb_array_length(options) > 0);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_pkey PRIMARY KEY (question_id);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_status_check CHECK (status = ANY (ARRAY['PENDING'::text, 'ANSWERED'::text]));
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_source_id_source_version_conce_key UNIQUE (user_id, source_id, source_version, concept_id, question_id);
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_source_id_source_version_sessi_key UNIQUE (user_id, source_id, source_version, session_id, concept_id, question_id);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_request_hash_check CHECK (learning_session_id IS NULL OR request_hash IS NOT NULL AND request_hash ~ '^[0-9a-f]{64}$'::text);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_assessment_type_check CHECK (assessment_type = ANY (ARRAY['DIAGNOSTIC'::text, 'REASSESSMENT'::text]));
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_concept_snapshot_check CHECK (jsonb_typeof(concept_snapshot) = 'object'::text);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_current_index_check CHECK (current_index >= 0);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_pkey PRIMARY KEY (session_id);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_status_check CHECK (status = ANY (ARRAY['PLANNING'::text, 'GENERATING'::text, 'VALIDATING'::text, 'READY'::text, 'SUBMITTED'::text, 'EXPIRED'::text, 'FAILED'::text]));
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_submission_response_check CHECK (submission_response IS NULL OR jsonb_typeof(submission_response) = 'object'::text);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_submitted_answers_check CHECK (submitted_answers IS NULL OR jsonb_typeof(submitted_answers) = 'object'::text);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_user_id_source_id_source_version_sessio_key UNIQUE (user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_attempt_count_check CHECK (attempt_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_check CHECK ((correct_count + incorrect_count) = attempt_count);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_check1 CHECK (reassessment_correct_count <= reassessment_attempt_count);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_check2 CHECK (reassessment_attempt_count <= attempt_count);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_consecutive_correct_check CHECK (consecutive_correct >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_correct_count_check CHECK (correct_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_incorrect_count_check CHECK (incorrect_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_lifetime_accuracy_check CHECK (lifetime_accuracy >= 0::double precision AND lifetime_accuracy <= 100::double precision);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_mastery_score_check CHECK (mastery_score >= 0::double precision AND mastery_score <= 100::double precision);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_mastery_state_check CHECK (mastery_state = ANY (ARRAY['UNASSESSED'::text, 'LEARNING'::text, 'WEAK'::text, 'REMEDIATING'::text, 'REASSESSING'::text, 'MASTERED'::text, 'NEEDS_SUPPORT'::text]));
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_pkey PRIMARY KEY (mastery_id);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_reassessment_attempt_count_check CHECK (reassessment_attempt_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_reassessment_correct_count_check CHECK (reassessment_correct_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_remediation_attempt_count_check CHECK (remediation_attempt_count >= 0);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_check CHECK (concept_id <> related_concept_id);
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_pkey PRIMARY KEY (source_id, source_version, concept_id, related_concept_id, relationship_type);
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_relationship_type_check CHECK (relationship_type = ANY (ARRAY['prerequisite'::text, 'related'::text]));
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_membership_pair_check CHECK ((subtopic_id IS NULL) = (sequence IS NULL));
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_pkey PRIMARY KEY (source_id, source_version, concept_id);
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_sequence_check CHECK (sequence >= 0);
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_user_id_source_id_source_version_concept_id_key UNIQUE (user_id, source_id, source_version, concept_id);
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_check CHECK (char_start IS NULL AND char_end IS NULL OR char_start IS NOT NULL AND char_end IS NOT NULL AND char_start >= 0 AND char_end > char_start);
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_extraction_confidence_check CHECK (extraction_confidence >= 0::numeric AND extraction_confidence <= 1::numeric);
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_pkey PRIMARY KEY (user_id, source_id, source_version, content_id, concept_id, support_kind);
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_support_kind_check CHECK (support_kind = ANY (ARRAY['definition'::text, 'explanation'::text, 'example'::text, 'prerequisite_evidence'::text]));
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_bbox_check CHECK (bbox IS NULL OR jsonb_typeof(bbox) = 'array'::text AND jsonb_array_length(bbox) = 4);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_check CHECK (parent_content_id IS NULL OR parent_content_id <> content_id);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_check1 CHECK (timestamp_end IS NULL OR timestamp_start IS NULL OR timestamp_end >= timestamp_start);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_confidence_score_check CHECK (confidence_score >= 0::double precision AND confidence_score <= 1::double precision);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_layer_check CHECK (layer = 'A'::text);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_modality_check CHECK (modality = ANY (ARRAY['pdf'::text, 'image'::text, 'txt'::text, 'video'::text]));
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_pkey PRIMARY KEY (source_id, source_version, content_id);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_sequence_index_check CHECK (sequence_index >= 0);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_timestamp_start_check CHECK (timestamp_start IS NULL OR timestamp_start >= 0::double precision);
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_user_id_source_id_source_version_content_id_key UNIQUE (user_id, source_id, source_version, content_id);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_duration_seconds_check CHECK (duration_seconds >= 0::double precision);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_output_metadata_check CHECK (jsonb_typeof(output_metadata) = 'object'::text);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_pkey PRIMARY KEY (job_id);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_plan_check CHECK (plan IS NULL OR jsonb_typeof(plan) = 'object'::text);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_progress_check CHECK (progress >= 0 AND progress <= 100);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_status_check CHECK (status = ANY (ARRAY['QUEUED'::text, 'PLANNING'::text, 'RENDERING'::text, 'GENERATING_AUDIO'::text, 'ALIGNING'::text, 'COMPOSITING'::text, 'COMPLETED'::text, 'FAILED'::text]));
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_user_id_source_id_source_version_concept_i_key UNIQUE (user_id, source_id, source_version, concept_id, job_id);
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_concept_masteries_check CHECK (jsonb_typeof(concept_masteries) = 'object'::text);
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_overall_score_check CHECK (overall_score >= 0::double precision AND overall_score <= 100::double precision);
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_pkey PRIMARY KEY (user_id, source_id, source_version);
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_total_sessions_check CHECK (total_sessions >= 0);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_assessment_scope_key UNIQUE (user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_mastery_revision_check CHECK (mastery_revision >= 0);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_pkey PRIMARY KEY (session_id);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_selected_concept_ids_check CHECK (cardinality(selected_concept_ids) >= 1 AND cardinality(selected_concept_ids) <= 64 AND array_position(selected_concept_ids, NULL::text) IS NULL);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_state_check CHECK (state = ANY (ARRAY['ACTIVE'::text, 'COMPLETED'::text, 'ABANDONED'::text]));
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_confidence_state_check CHECK (confidence_state = ANY (ARRAY['POSSIBLE'::text, 'LIKELY'::text, 'CONFIRMED'::text]));
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_occurrence_count_check CHECK (occurrence_count >= 1);
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_pkey PRIMARY KEY (misconception_id);
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_status_check CHECK (status = ANY (ARRAY['ACTIVE'::text, 'CORRECTED'::text, 'RECURRENT'::text]));
ALTER TABLE visualai_learning.profiles ADD CONSTRAINT profiles_learning_preferences_shape CHECK (learning_preferences = '{}'::jsonb OR COALESCE(jsonb_typeof(learning_preferences) = 'object'::text AND learning_preferences ?& ARRAY['education_level'::text, 'interested_domains'::text, 'custom_interest'::text, 'preferred_language'::text, 'learning_goal'::text, 'personalization_enabled'::text] AND (learning_preferences - ARRAY['education_level'::text, 'interested_domains'::text, 'custom_interest'::text, 'preferred_language'::text, 'learning_goal'::text, 'personalization_enabled'::text]) = '{}'::jsonb AND ((learning_preferences ->> 'education_level'::text) = ANY (ARRAY['Primary'::text, 'Secondary'::text, 'Undergraduate'::text, 'Other'::text])) AND
CASE
    WHEN jsonb_typeof(learning_preferences -> 'interested_domains'::text) = 'array'::text THEN jsonb_array_length(learning_preferences -> 'interested_domains'::text) >= 1 AND jsonb_array_length(learning_preferences -> 'interested_domains'::text) <= 12 AND (learning_preferences -> 'interested_domains'::text) <@ '["Sports", "Dance", "Music", "Gaming", "Technology", "Science", "Nature and Animals", "Art and Design", "Movies and Animation", "Business and Entrepreneurship", "Fitness", "Other"]'::jsonb
    ELSE false
END AND jsonb_typeof(learning_preferences -> 'custom_interest'::text) = 'string'::text AND length(learning_preferences ->> 'custom_interest'::text) <= 80 AND ((learning_preferences -> 'interested_domains'::text) ? 'Other'::text) = (length(TRIM(BOTH FROM learning_preferences ->> 'custom_interest'::text)) > 0) AND (learning_preferences ->> 'preferred_language'::text) = 'English'::text AND ((learning_preferences ->> 'learning_goal'::text) = ANY (ARRAY[''::text, 'Exam preparation'::text, 'Concept understanding'::text, 'Revision'::text, 'Skill development'::text])) AND jsonb_typeof(learning_preferences -> 'personalization_enabled'::text) = 'boolean'::text, false));
ALTER TABLE visualai_learning.profiles ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);
ALTER TABLE visualai_learning.profiles ADD CONSTRAINT profiles_role_check CHECK (role = ANY (ARRAY['student'::text, 'instructor'::text, 'admin'::text]));
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_attempt_number_check CHECK (attempt_number >= 1);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_duration_seconds_check CHECK (duration_seconds IS NULL OR duration_seconds >= 0::double precision);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_metadata_check CHECK (jsonb_typeof(metadata) = 'object'::text);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_pkey PRIMARY KEY (remediation_job_id);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_status_check CHECK (status = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, 'READY'::text, 'FAILED'::text]));
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_source_id_source_version_idempoten_key UNIQUE (user_id, source_id, source_version, idempotency_key);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT knowledge_commit_metadata_check CHECK (knowledge_state = 'READY'::text AND knowledge_schema_version = 1 AND knowledge_schema_version IS NOT NULL AND knowledge_operation_id IS NOT NULL AND knowledge_payload_hash IS NOT NULL AND knowledge_payload_hash ~ '^[0-9a-f]{64}$'::text AND knowledge_committed_at IS NOT NULL OR knowledge_state <> 'READY'::text AND knowledge_schema_version IS NULL AND knowledge_operation_id IS NULL AND knowledge_payload_hash IS NULL AND knowledge_committed_at IS NULL);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_file_location_check CHECK (file_location <> ''::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_knowledge_diagnostics_check CHECK (jsonb_typeof(knowledge_diagnostics) = 'object'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_knowledge_state_check CHECK (knowledge_state = ANY (ARRAY['PENDING'::text, 'READY'::text, 'FAILED'::text, 'LEGACY_UNMAPPED'::text]));
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_normalized_content_check CHECK (jsonb_typeof(normalized_content) = 'array'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_pkey PRIMARY KEY (source_id, version);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_quarantined_content_check CHECK (jsonb_typeof(quarantined_content) = 'array'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_rich_chunks_check CHECK (jsonb_typeof(rich_chunks) = 'array'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_sanitized_content_check CHECK (jsonb_typeof(sanitized_content) = 'array'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_source_id_source_version_key UNIQUE (source_id, source_version);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_topic_blueprint_check CHECK (topic_blueprint IS NULL OR jsonb_typeof(topic_blueprint) = 'object'::text);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_user_id_source_id_version_key UNIQUE (user_id, source_id, version);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_user_id_source_id_version_source_version_key UNIQUE (user_id, source_id, version, source_version);
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_version_check CHECK (version > 0);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_check CHECK (parent_source_id IS NULL OR parent_source_id <> source_id);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_file_size_check CHECK (file_size >= 0);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_pkey PRIMARY KEY (source_id);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_source_id_check CHECK (source_id <> ''::text);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_source_type_check CHECK (source_type = ANY (ARRAY['pdf'::text, 'txt'::text, 'image'::text, 'video'::text]));
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_status_check CHECK (status = ANY (ARRAY['UPLOADED'::text, 'PROCESSING'::text, 'EXTRACTING'::text, 'NORMALIZING'::text, 'INDEXING'::text, 'READY'::text, 'FAILED'::text, 'VISION_EXTRACTION_FAILED'::text]));
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_user_id_source_id_key UNIQUE (user_id, source_id);
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_version_check CHECK (version > 0);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_pkey PRIMARY KEY (user_id, source_id, source_version, subtopic_id);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_sequence_check CHECK (sequence >= 0);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_subtopic_id_check CHECK (subtopic_id <> ''::text);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_title_check CHECK (btrim(title) <> ''::text);
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_user_id_source_id_source_version_topic_id_sequenc_key UNIQUE (user_id, source_id, source_version, topic_id, sequence);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_pkey PRIMARY KEY (user_id, source_id, source_version, topic_id);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_provenance_check CHECK (jsonb_typeof(provenance) = 'object'::text);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_sequence_check CHECK (sequence >= 0);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_title_check CHECK (btrim(title) <> ''::text);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_topic_id_check CHECK (topic_id <> ''::text);
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_user_id_source_id_source_version_sequence_key UNIQUE (user_id, source_id, source_version, sequence);
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_payload_check CHECK (jsonb_typeof(payload) = 'object'::text);
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_pkey PRIMARY KEY (user_id, source_id, source_version);
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_schema_version_check CHECK (schema_version > 0);
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_source_version_check CHECK (source_version > 0);
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_conc_fkey1 FOREIGN KEY (user_id, source_id, source_version, concept_id, question_id) REFERENCES visualai_learning.assessment_questions(user_id, source_id, source_version, concept_id, question_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_conce_fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_sess_fkey1 FOREIGN KEY (user_id, source_id, source_version, session_id, concept_id, question_id) REFERENCES visualai_learning.assessment_questions(user_id, source_id, source_version, session_id, concept_id, question_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_attempts ADD CONSTRAINT assessment_attempts_user_id_source_id_source_version_sessi_fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_source_id_source_version_conc_fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.assessment_questions ADD CONSTRAINT assessment_questions_user_id_source_id_source_version_sess_fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_learning_session_scope_fk FOREIGN KEY (user_id, source_id, source_version, learning_session_id) REFERENCES visualai_learning.learning_sessions(user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_remediation_fk FOREIGN KEY (reassessment_job_id) REFERENCES visualai_learning.remediation_jobs(remediation_job_id);
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.assessment_sessions ADD CONSTRAINT assessment_sessions_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_learning_scope_fk FOREIGN KEY (user_id, source_id, source_version, learning_session_id) REFERENCES visualai_learning.learning_sessions(user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_user_id_source_id_source_version_concept_i_fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_mastery ADD CONSTRAINT concept_mastery_user_id_source_id_source_version_session_i_fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_user_id_source_id_source_version_con_fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concept_relationships ADD CONSTRAINT concept_relationships_user_id_source_id_source_version_rel_fkey FOREIGN KEY (user_id, source_id, source_version, related_concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_subtopic_scope_fk FOREIGN KEY (user_id, source_id, source_version, subtopic_id) REFERENCES visualai_learning.subtopics(user_id, source_id, source_version, subtopic_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.concepts ADD CONSTRAINT concepts_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_user_id_source_id_source_version_concept__fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.content_concepts ADD CONSTRAINT content_concepts_user_id_source_id_source_version_content__fkey FOREIGN KEY (user_id, source_id, source_version, content_id) REFERENCES visualai_learning.content_units(user_id, source_id, source_version, content_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.content_units ADD CONSTRAINT content_units_user_id_source_id_source_version_parent_cont_fkey FOREIGN KEY (user_id, source_id, source_version, parent_content_id) REFERENCES visualai_learning.content_units(user_id, source_id, source_version, content_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_user_id_source_id_source_version_concept__fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.generated_videos ADD CONSTRAINT generated_videos_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.learning_profiles ADD CONSTRAINT learning_profiles_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_user_id_source_id_source_version_subtopi_fkey FOREIGN KEY (user_id, source_id, source_version, subtopic_id) REFERENCES visualai_learning.subtopics(user_id, source_id, source_version, subtopic_id);
ALTER TABLE visualai_learning.learning_sessions ADD CONSTRAINT learning_sessions_user_id_source_id_source_version_topic_i_fkey FOREIGN KEY (user_id, source_id, source_version, topic_id) REFERENCES visualai_learning.topics(user_id, source_id, source_version, topic_id);
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_learning_scope_fk FOREIGN KEY (user_id, source_id, source_version, learning_session_id) REFERENCES visualai_learning.learning_sessions(user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_user_id_source_id_source_version_concept_id_fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.misconceptions ADD CONSTRAINT misconceptions_user_id_source_id_source_version_session_id_fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_learning_scope_fk FOREIGN KEY (user_id, source_id, source_version, learning_session_id) REFERENCES visualai_learning.learning_sessions(user_id, source_id, source_version, session_id);
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_source_id_source_version_concept__fkey FOREIGN KEY (user_id, source_id, source_version, concept_id) REFERENCES visualai_learning.concepts(user_id, source_id, source_version, concept_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_source_id_source_version_concept_fkey1 FOREIGN KEY (user_id, source_id, source_version, concept_id, video_job_id) REFERENCES visualai_learning.generated_videos(user_id, source_id, source_version, concept_id, job_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.remediation_jobs ADD CONSTRAINT remediation_jobs_user_id_source_id_source_version_session__fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.source_versions ADD CONSTRAINT source_versions_user_id_source_id_fkey FOREIGN KEY (user_id, source_id) REFERENCES visualai_learning.sources(user_id, source_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_current_version_fk FOREIGN KEY (user_id, source_id, version, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version, source_version) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.sources ADD CONSTRAINT sources_user_id_parent_source_id_fkey FOREIGN KEY (user_id, parent_source_id) REFERENCES visualai_learning.sources(user_id, source_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE visualai_learning.subtopics ADD CONSTRAINT subtopics_user_id_source_id_source_version_topic_id_fkey FOREIGN KEY (user_id, source_id, source_version, topic_id) REFERENCES visualai_learning.topics(user_id, source_id, source_version, topic_id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.topics ADD CONSTRAINT topics_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_user_id_fkey FOREIGN KEY (user_id) REFERENCES visualai_learning.profiles(id) ON DELETE CASCADE;
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_user_id_source_id_source_version_fkey FOREIGN KEY (user_id, source_id, source_version) REFERENCES visualai_learning.source_versions(user_id, source_id, version) ON DELETE CASCADE;
ALTER TABLE visualai_learning.video_target_matrices ADD CONSTRAINT video_target_matrices_user_id_source_id_source_version_ses_fkey FOREIGN KEY (user_id, source_id, source_version, session_id) REFERENCES visualai_learning.assessment_sessions(user_id, source_id, source_version, session_id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX assessment_attempts_lookup_3_idx ON visualai_learning.assessment_attempts USING btree (user_id, source_id, source_version, concept_id, question_id);
CREATE INDEX assessment_attempts_lookup_1_idx ON visualai_learning.assessment_attempts USING btree (user_id, source_id, source_version, concept_id, submitted_at);
CREATE INDEX assessment_attempts_lookup_2_idx ON visualai_learning.assessment_attempts USING btree (user_id, source_id, source_version, session_id);
CREATE INDEX assessment_questions_lookup_2_idx ON visualai_learning.assessment_questions USING btree (user_id, source_id, source_version, concept_id);
CREATE INDEX assessment_questions_lookup_1_idx ON visualai_learning.assessment_questions USING btree (user_id, source_id, source_version, session_id);
CREATE INDEX assessment_sessions_lookup_1_idx ON visualai_learning.assessment_sessions USING btree (user_id, source_id, source_version, status);
CREATE INDEX assessment_learning_session_lookup ON visualai_learning.assessment_sessions USING btree (user_id, learning_session_id);
CREATE INDEX concept_mastery_learning_lookup ON visualai_learning.concept_mastery USING btree (user_id, learning_session_id);
CREATE INDEX concept_mastery_lookup_1_idx ON visualai_learning.concept_mastery USING btree (user_id, source_id, source_version, session_id);
CREATE UNIQUE INDEX concept_mastery_learning_scope ON visualai_learning.concept_mastery USING btree (user_id, source_id, source_version, learning_session_id, concept_id) WHERE (learning_session_id IS NOT NULL);
CREATE UNIQUE INDEX concept_mastery_legacy_scope ON visualai_learning.concept_mastery USING btree (user_id, source_id, source_version, concept_id) WHERE (learning_session_id IS NULL);
CREATE INDEX concept_mastery_lookup_2_idx ON visualai_learning.concept_mastery USING btree (user_id, mastery_state);
CREATE INDEX concept_relationships_lookup_2_idx ON visualai_learning.concept_relationships USING btree (user_id, source_id, source_version, related_concept_id);
CREATE INDEX concept_relationships_lookup_1_idx ON visualai_learning.concept_relationships USING btree (user_id, source_id, source_version, concept_id);
CREATE INDEX concepts_lookup_1_idx ON visualai_learning.concepts USING btree (user_id, source_id, source_version);
CREATE UNIQUE INDEX concepts_subtopic_sequence_idx ON visualai_learning.concepts USING btree (user_id, source_id, source_version, subtopic_id, sequence) WHERE (subtopic_id IS NOT NULL);
CREATE INDEX content_concepts_concept_idx ON visualai_learning.content_concepts USING btree (user_id, source_id, source_version, concept_id, content_id);
CREATE INDEX content_units_lookup_2_idx ON visualai_learning.content_units USING btree (user_id, source_id, source_version, parent_content_id);
CREATE INDEX content_units_lookup_1_idx ON visualai_learning.content_units USING btree (user_id, source_id, source_version, sequence_index);
CREATE INDEX generated_videos_lookup_1_idx ON visualai_learning.generated_videos USING btree (user_id, source_id, source_version, concept_id);
CREATE INDEX generated_videos_lookup_2_idx ON visualai_learning.generated_videos USING btree (user_id, status);
CREATE INDEX learning_profiles_lookup_1_idx ON visualai_learning.learning_profiles USING btree (user_id, source_id, source_version);
CREATE INDEX learning_sessions_owner_active_idx ON visualai_learning.learning_sessions USING btree (user_id, last_active_at DESC);
CREATE INDEX misconceptions_lookup_2_idx ON visualai_learning.misconceptions USING btree (user_id, source_id, source_version, session_id);
CREATE INDEX misconceptions_lookup_1_idx ON visualai_learning.misconceptions USING btree (user_id, source_id, source_version, concept_id, status);
CREATE INDEX misconceptions_learning_lookup ON visualai_learning.misconceptions USING btree (user_id, learning_session_id);
CREATE UNIQUE INDEX misconceptions_learning_scope ON visualai_learning.misconceptions USING btree (user_id, learning_session_id, concept_id) WHERE (learning_session_id IS NOT NULL);
CREATE INDEX remediation_jobs_lookup_3_idx ON visualai_learning.remediation_jobs USING btree (user_id, source_id, source_version, concept_id, video_job_id);
CREATE INDEX remediation_jobs_lookup_1_idx ON visualai_learning.remediation_jobs USING btree (user_id, source_id, source_version, concept_id, status);
CREATE INDEX remediation_jobs_learning_lookup ON visualai_learning.remediation_jobs USING btree (user_id, learning_session_id);
CREATE INDEX remediation_jobs_lookup_2_idx ON visualai_learning.remediation_jobs USING btree (user_id, source_id, source_version, session_id);
CREATE INDEX source_versions_lookup_1_idx ON visualai_learning.source_versions USING btree (user_id, source_id, version);
CREATE UNIQUE INDEX source_versions_knowledge_operation_idx ON visualai_learning.source_versions USING btree (user_id, knowledge_operation_id) WHERE (knowledge_operation_id IS NOT NULL);
CREATE INDEX sources_lookup_1_idx ON visualai_learning.sources USING btree (user_id, file_hash);
CREATE INDEX sources_current_version_fk_idx ON visualai_learning.sources USING btree (user_id, source_id, version, source_version);
CREATE INDEX sources_lookup_2_idx ON visualai_learning.sources USING btree (user_id, status);
CREATE INDEX sources_lookup_3_idx ON visualai_learning.sources USING btree (user_id, parent_source_id);
CREATE INDEX video_target_matrices_lookup_1_idx ON visualai_learning.video_target_matrices USING btree (user_id, source_id, source_version, session_id);

CREATE OR REPLACE FUNCTION visualai_learning_private.assessment_transaction(p_action text, p_user_id uuid, p_assessment_id text, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    job visualai_learning.remediation_jobs;
    learning visualai_learning.learning_sessions;
    assessment visualai_learning.assessment_sessions;
    result jsonb;
BEGIN
    IF p_user_id IS DISTINCT FROM visualai_learning_private.owner_id() THEN
        RAISE EXCEPTION 'Owner unavailable' USING ERRCODE='42501';
    END IF;
    -- Lock learning before assessment, matching mastery finalization lock order.
    IF p_action='create' THEN
        SELECT * INTO learning FROM visualai_learning.learning_sessions WHERE session_id=(p_payload->>'learning_session_id')::uuid AND user_id=p_user_id FOR UPDATE;
    ELSE
        SELECT * INTO assessment FROM visualai_learning.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id;
        IF assessment.learning_session_id IS NOT NULL THEN
            SELECT * INTO learning FROM visualai_learning.learning_sessions WHERE session_id=assessment.learning_session_id AND user_id=p_user_id FOR UPDATE;
        END IF;
    END IF;
    IF p_action='create' AND NOT EXISTS(SELECT 1 FROM visualai_learning.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id) THEN
        -- One outstanding assessment per learning scope prevents stale-cycle outcomes.
        IF EXISTS(SELECT 1 FROM visualai_learning.assessment_sessions WHERE user_id=p_user_id AND learning_session_id=learning.session_id
            AND (status='READY' OR (status='SUBMITTED' AND mastery_applied_at IS NULL))) THEN
            RAISE EXCEPTION 'Assessment finalization pending' USING ERRCODE='23505';
        END IF;
        IF p_payload->>'reassessment_job_id' IS NULL AND EXISTS(SELECT 1 FROM visualai_learning.concept_mastery m
            WHERE m.user_id=p_user_id AND m.learning_session_id=learning.session_id
            AND m.concept_id IN (SELECT jsonb_array_elements_text(p_payload->'concept_queue'))
            AND m.mastery_state IN ('REMEDIATING','REASSESSING','NEEDS_SUPPORT')) THEN
            RAISE EXCEPTION 'Learning progression unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    IF p_action='create' AND p_payload->>'reassessment_job_id' IS NOT NULL THEN
        SELECT * INTO job FROM visualai_learning.remediation_jobs WHERE remediation_job_id=p_payload->>'reassessment_job_id'
            AND user_id=p_user_id AND learning_session_id=learning.session_id
            AND source_id=learning.source_id AND source_version=learning.source_version FOR UPDATE;
        IF job.remediation_job_id IS NULL OR job.status<>'READY' OR job.metadata->>'completed' IS DISTINCT FROM 'true'
           OR NOT EXISTS(SELECT 1 FROM visualai_learning.concept_mastery m WHERE m.user_id=p_user_id AND m.learning_session_id=learning.session_id
                AND m.concept_id=job.concept_id AND m.mastery_state='REASSESSING' AND m.remediation_attempt_count=job.attempt_number)
           OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'concept_queue') c(id) WHERE id<>job.concept_id) THEN
            RAISE EXCEPTION 'Reassessment unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    IF p_action='submit' AND assessment.reassessment_job_id IS NOT NULL THEN
        IF NOT EXISTS(SELECT 1 FROM visualai_learning.remediation_jobs j JOIN visualai_learning.concept_mastery m
            ON m.user_id=j.user_id AND m.learning_session_id=j.learning_session_id AND m.concept_id=j.concept_id
            WHERE j.remediation_job_id=assessment.reassessment_job_id AND j.user_id=p_user_id
            AND m.mastery_state='REASSESSING' AND m.remediation_attempt_count=j.attempt_number)
            AND assessment.status<>'SUBMITTED' THEN
            RAISE EXCEPTION 'Reassessment unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    result := visualai_learning_private.assessment_transaction_phase9(p_action,p_user_id,p_assessment_id,p_payload);
    IF p_action='create' AND p_payload->>'reassessment_job_id' IS NOT NULL THEN
        UPDATE visualai_learning.assessment_sessions SET assessment_type='REASSESSMENT',reassessment_job_id=job.remediation_job_id WHERE session_id=p_assessment_id AND user_id=p_user_id;
        result := visualai_learning_private.assessment_transaction_phase9('load',p_user_id,p_assessment_id,'{}');
    ELSIF p_action='submit' THEN
        UPDATE visualai_learning.assessment_attempts a SET assessment_type=s.assessment_type FROM visualai_learning.assessment_sessions s
            WHERE a.session_id=s.session_id AND a.user_id=s.user_id AND s.session_id=p_assessment_id AND s.user_id=p_user_id;
    END IF;
    RETURN result;
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.assessment_transaction_phase9(p_action text, p_user_id uuid, p_assessment_id text, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    assessment visualai_learning.assessment_sessions;
    learning visualai_learning.learning_sessions;
    q jsonb;
    stored visualai_learning.assessment_questions;
    count_questions integer;
    selected integer;
    question_results jsonb := '[]'::jsonb;
    concept_results jsonb;
    performance jsonb;
BEGIN
    IF p_user_id IS DISTINCT FROM visualai_learning_private.owner_id() THEN
        RAISE EXCEPTION 'Owner unavailable' USING ERRCODE='42501';
    END IF;
    IF p_user_id IS NULL OR p_assessment_id IS NULL OR length(p_assessment_id)>128
       OR p_action NOT IN ('load','create','submit') OR p_action IS NULL THEN
        RAISE EXCEPTION 'Invalid assessment operation' USING ERRCODE='22023';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_assessment_id,0));
    SELECT * INTO assessment FROM visualai_learning.assessment_sessions
        WHERE session_id=p_assessment_id AND user_id=p_user_id FOR UPDATE;
    IF p_action='create' THEN
        IF jsonb_typeof(p_payload) IS DISTINCT FROM 'object'
           OR p_payload->>'session_id' IS DISTINCT FROM p_assessment_id
           OR p_payload->>'student_id' IS DISTINCT FROM p_user_id::text
           OR p_payload->>'request_hash' IS NULL
           OR p_payload->>'request_hash' !~ '^[0-9a-f]{64}$'
           OR jsonb_typeof(p_payload->'questions') IS DISTINCT FROM 'array'
           OR jsonb_typeof(p_payload->'concept_queue') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Invalid assessment payload' USING ERRCODE='22023';
        END IF;
        IF assessment.session_id IS NOT NULL THEN
            IF assessment.request_hash IS DISTINCT FROM p_payload->>'request_hash' THEN
                RAISE EXCEPTION 'Assessment conflict' USING ERRCODE='23505';
            END IF;
        ELSE
            -- Same owner/version session; lock prevents selection/state changes mid-creation.
            SELECT * INTO learning FROM visualai_learning.learning_sessions
                WHERE session_id=(p_payload->>'learning_session_id')::uuid AND user_id=p_user_id FOR UPDATE;
            count_questions := jsonb_array_length(p_payload->'questions');
            IF learning.session_id IS NULL OR learning.state<>'ACTIVE'
               OR learning.source_id IS DISTINCT FROM p_payload->>'source_id'
               OR learning.source_version IS DISTINCT FROM (p_payload->>'source_version')::integer
               OR count_questions NOT BETWEEN 1 AND 20
               OR jsonb_array_length(p_payload->'concept_queue')<>count_questions
               OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(p_payload->'concept_queue') t(cid)
                          WHERE NOT (cid=ANY(learning.selected_concept_ids))) THEN
                RAISE EXCEPTION 'Assessment scope unavailable' USING ERRCODE='22023';
            END IF;
            INSERT INTO visualai_learning.assessment_sessions(session_id,user_id,source_id,source_version,
                learning_session_id,request_hash,status,concept_queue)
            VALUES(p_assessment_id,p_user_id,learning.source_id,learning.source_version,learning.session_id,
                p_payload->>'request_hash','READY',ARRAY(SELECT jsonb_array_elements_text(p_payload->'concept_queue')));
            FOR q IN SELECT value FROM jsonb_array_elements(p_payload->'questions') LOOP
                IF q->>'source_id' IS DISTINCT FROM learning.source_id
                   OR (q->>'source_version')::integer IS DISTINCT FROM learning.source_version
                   OR q->>'concept_id' IS NULL OR NOT (q->>'concept_id'=ANY(learning.selected_concept_ids))
                   OR jsonb_typeof(q->'options') IS DISTINCT FROM 'array'
                   OR jsonb_array_length(q->'options')<>4
                   OR jsonb_typeof(q->'evidence_ids') IS DISTINCT FROM 'array'
                   OR jsonb_array_length(q->'evidence_ids')<1
                   OR (q->>'correct_index')::integer NOT BETWEEN 0 AND 3 THEN
                    RAISE EXCEPTION 'Invalid assessment question' USING ERRCODE='22023';
                END IF;
                INSERT INTO visualai_learning.assessment_questions(question_id,user_id,source_id,source_version,session_id,
                    concept_id,concept_name,stem,options,correct_index,explanation,difficulty,evidence_quote,evidence_text,
                    chunk_ids,content_ids,evidence_ids,page_start,page_end,timestamp_start,timestamp_end)
                VALUES(q->>'question_id',p_user_id,learning.source_id,learning.source_version,p_assessment_id,
                    q->>'concept_id',q->>'concept_name',q->>'stem',q->'options',(q->>'correct_index')::integer,
                    q->>'explanation',q->>'difficulty',q->>'evidence_quote',q->>'evidence_text',
                    ARRAY(SELECT jsonb_array_elements_text(q->'chunk_ids')),
                    ARRAY(SELECT jsonb_array_elements_text(q->'content_ids')),
                    ARRAY(SELECT jsonb_array_elements_text(q->'evidence_ids')),
                    (q->>'page_start')::integer,(q->>'page_end')::integer,q->>'timestamp_start',q->>'timestamp_end');
            END LOOP;
            SELECT * INTO assessment FROM visualai_learning.assessment_sessions WHERE session_id=p_assessment_id;
        END IF;
    ELSIF p_action='submit' THEN
        IF assessment.session_id IS NULL THEN RETURN NULL; END IF;
        SELECT * INTO learning FROM visualai_learning.learning_sessions
            WHERE session_id=assessment.learning_session_id AND user_id=p_user_id FOR UPDATE;
        IF learning.session_id IS NULL OR learning.state<>'ACTIVE'
           OR NOT (assessment.concept_queue <@ learning.selected_concept_ids) THEN
            RAISE EXCEPTION 'Assessment conflict' USING ERRCODE='23505';
        END IF;
        IF assessment.status='SUBMITTED' THEN
            IF assessment.submitted_answers IS DISTINCT FROM p_payload->'answers' THEN
                RAISE EXCEPTION 'Assessment conflict' USING ERRCODE='23505';
            END IF;
        ELSE
            SELECT count(*) INTO count_questions FROM visualai_learning.assessment_questions
                WHERE session_id=p_assessment_id AND user_id=p_user_id;
            IF assessment.status<>'READY' OR count_questions=0
               OR jsonb_typeof(p_payload->'answers') IS DISTINCT FROM 'object'
               OR (SELECT count(*) FROM jsonb_object_keys(p_payload->'answers'))<>count_questions
               OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_payload->'answers') a(id)
                   WHERE NOT EXISTS(SELECT 1 FROM visualai_learning.assessment_questions q2
                       WHERE q2.session_id=p_assessment_id AND q2.user_id=p_user_id AND q2.question_id=a.id)) THEN
                RAISE EXCEPTION 'Invalid assessment answers' USING ERRCODE='22023';
            END IF;
            FOR stored IN SELECT * FROM visualai_learning.assessment_questions
                WHERE session_id=p_assessment_id AND user_id=p_user_id ORDER BY question_id LOOP
                IF jsonb_typeof(p_payload->'answers'->stored.question_id) IS DISTINCT FROM 'number'
                   OR (p_payload->'answers'->>stored.question_id) !~ '^[0-3]$' THEN
                    RAISE EXCEPTION 'Invalid assessment answers' USING ERRCODE='22023';
                END IF;
                selected := (p_payload->'answers'->>stored.question_id)::integer;
                INSERT INTO visualai_learning.assessment_attempts(attempt_id,user_id,source_id,source_version,session_id,
                    concept_id,question_id,assessment_type,selected_answer,correct_answer,is_correct)
                VALUES(p_assessment_id||':'||stored.question_id,p_user_id,assessment.source_id,assessment.source_version,
                    p_assessment_id,stored.concept_id,stored.question_id,'DIAGNOSTIC',selected,stored.correct_index,
                    selected=stored.correct_index);
                question_results := question_results || jsonb_build_array(jsonb_build_object(
                    'question_id',stored.question_id,'concept_id',stored.concept_id,
                    'selected_index',selected,'correct',selected=stored.correct_index));
            END LOOP;
            SELECT jsonb_agg(jsonb_build_object('concept_id',concept_id,'attempted',attempted,'correct',correct,
                'incorrect',attempted-correct,'percentage',100.0*correct/attempted) ORDER BY concept_id)
            INTO concept_results FROM (
                SELECT concept_id,count(*) attempted,count(*) FILTER(WHERE is_correct) correct
                FROM visualai_learning.assessment_attempts WHERE session_id=p_assessment_id AND user_id=p_user_id GROUP BY concept_id
            ) t;
            performance := jsonb_build_object('session_id',p_assessment_id,'learning_session_id',assessment.learning_session_id,
                'source_id',assessment.source_id,'source_version',assessment.source_version,
                'question_results',question_results,'concept_results',concept_results,'overall_score',
                (SELECT 100.0*count(*) FILTER(WHERE is_correct)/count(*) FROM visualai_learning.assessment_attempts
                    WHERE session_id=p_assessment_id AND user_id=p_user_id));
            UPDATE visualai_learning.assessment_sessions SET status='SUBMITTED',submitted_answers=p_payload->'answers',
                submission_response=performance,submitted_at=clock_timestamp()
                WHERE session_id=p_assessment_id AND user_id=p_user_id;
            SELECT * INTO assessment FROM visualai_learning.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id;
        END IF;
    END IF;
    IF assessment.session_id IS NULL THEN RETURN NULL; END IF;
    RETURN to_jsonb(assessment) || jsonb_build_object('student_id',p_user_id::text,'questions',
        (SELECT coalesce(jsonb_agg(to_jsonb(q3) ORDER BY question_id),'[]'::jsonb)
         FROM visualai_learning.assessment_questions q3 WHERE session_id=p_assessment_id AND user_id=p_user_id));
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.commit_knowledge_snapshot(p_source_id text, p_source_version integer, p_operation_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE
    caller uuid := visualai_learning_private.owner_id();
    snapshot visualai_learning.source_versions;
    payload_hash text;
    item jsonb;
    remaining text[];
    removable text[];
    remaining_edges jsonb;
    -- Initial operational caps, not educational thresholds. See deployment doc.
    max_bytes CONSTANT integer := 2097152;
    max_topics CONSTANT integer := 128;
    max_subtopics CONSTANT integer := 512;
    max_concepts CONSTANT integer := 1024;
    max_links CONSTANT integer := 8192;
    max_edges CONSTANT integer := 4096;
BEGIN
    IF caller IS NULL THEN
        RAISE EXCEPTION 'Authenticated identity required' USING ERRCODE = '42501';
    END IF;
    IF p_source_id IS NULL OR p_source_id !~ '^[A-Za-z0-9_-]{1,128}$'
        OR p_source_version IS NULL OR p_source_version < 1 OR p_operation_id IS NULL
        OR p_payload IS NULL OR pg_catalog.octet_length(p_payload::text) > max_bytes THEN
        RAISE EXCEPTION 'KNOWLEDGE_INVALID_REQUEST' USING ERRCODE = '22023';
    END IF;
    PERFORM visualai_learning_private.knowledge_object(p_payload,
        ARRAY['schema_version','topics','subtopics','concepts','content_concepts','relationships'],
        '{"schema_version":"number","topics":"array","subtopics":"array","concepts":"array","content_concepts":"array","relationships":"array"}');
    IF p_payload->>'schema_version' <> '1'
        OR pg_catalog.jsonb_array_length(p_payload->'topics') NOT BETWEEN 1 AND max_topics
        OR pg_catalog.jsonb_array_length(p_payload->'subtopics') NOT BETWEEN 1 AND max_subtopics
        OR pg_catalog.jsonb_array_length(p_payload->'concepts') NOT BETWEEN 1 AND max_concepts
        OR pg_catalog.jsonb_array_length(p_payload->'content_concepts') NOT BETWEEN 1 AND max_links
        OR pg_catalog.jsonb_array_length(p_payload->'relationships') > max_edges THEN
        RAISE EXCEPTION 'KNOWLEDGE_INVALID_SIZE_OR_VERSION' USING ERRCODE = '22023';
    END IF;
    -- Shape/type validation also applies to idempotent retries.
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'topics') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['topic_id','title','sequence','provenance'],
            '{"topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'subtopics') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['subtopic_id','topic_id','title','sequence','provenance'],
            '{"subtopic_id":"string","topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['concept_id','subtopic_id','name','sequence','provenance'],
            '{"concept_id":"string","subtopic_id":"string","name":"string","definition":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['content_id','concept_id','support_kind','provenance'],
            '{"content_id":"string","concept_id":"string","support_kind":"string","char_start":"number","char_end":"number","extraction_confidence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['concept_id','related_concept_id','relationship_type','evidence_content_ids','provenance'],
            '{"concept_id":"string","related_concept_id":"string","relationship_type":"string","evidence_content_ids":"array","provenance":"object"}');
        IF pg_catalog.jsonb_array_length(item->'evidence_content_ids') NOT BETWEEN 1 AND 64
            OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(item->'evidence_content_ids') e
                WHERE pg_catalog.jsonb_typeof(e.value) <> 'string') THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_EDGE_EVIDENCE' USING ERRCODE = '22023';
        END IF;
    END LOOP;

    payload_hash := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        visualai_learning_private.knowledge_canonical_json(p_payload)::text, 'UTF8')), 'hex');
    SELECT * INTO snapshot FROM visualai_learning.source_versions
        WHERE user_id = caller AND source_id = p_source_id AND version = p_source_version FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source version unavailable' USING ERRCODE = '42501';
    END IF;
    IF snapshot.knowledge_state = 'READY' THEN
        IF snapshot.knowledge_operation_id IS DISTINCT FROM p_operation_id
            OR snapshot.knowledge_payload_hash IS DISTINCT FROM payload_hash THEN
            RAISE EXCEPTION 'KNOWLEDGE_SNAPSHOT_CONFLICT' USING ERRCODE = '23505';
        END IF;
    ELSE
        -- Every concept is evidenced; every link resolves through this exact canonical scope.
        IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
            WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                WHERE l->>'concept_id' = c->>'concept_id'))
            OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                LEFT JOIN visualai_learning.content_units u ON u.user_id = caller AND u.source_id = p_source_id
                    AND u.source_version = p_source_version AND u.content_id = l->>'content_id'
                WHERE u.content_id IS NULL
                    OR ((l->>'char_start') IS NULL) <> ((l->>'char_end') IS NULL)
                    OR (l->>'char_start')::integer < 0
                    OR (l->>'char_end')::integer <= (l->>'char_start')::integer
                    OR (l->>'char_end')::integer > pg_catalog.char_length(u.text)
                    OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                        WHERE c->>'concept_id' = l->>'concept_id')) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_CONTENT_EVIDENCE' USING ERRCODE = '22023';
        END IF;
        -- A complete mapping must retain every historical concept and relationship.
        IF EXISTS (SELECT 1 FROM visualai_learning.concepts c WHERE c.user_id = caller AND c.source_id = p_source_id
                AND c.source_version = p_source_version AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') n
                    WHERE n->>'concept_id' = c.concept_id))
            OR EXISTS (SELECT 1 FROM visualai_learning.concept_relationships r WHERE r.user_id = caller
                AND r.source_id = p_source_id AND r.source_version = p_source_version AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') n
                    WHERE n->>'concept_id' = r.concept_id AND n->>'related_concept_id' = r.related_concept_id
                        AND n->>'relationship_type' = r.relationship_type)) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INCOMPLETE_LEGACY_MAPPING' USING ERRCODE = '22023';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') r
            WHERE r->>'relationship_type' NOT IN ('prerequisite','related')
                OR r->>'concept_id' = r->>'related_concept_id'
                OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                    WHERE c->>'concept_id' = r->>'concept_id')
                OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                    WHERE c->>'concept_id' = r->>'related_concept_id')
                OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements_text(r->'evidence_content_ids') e(id)
                    WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                        WHERE l->>'content_id' = e.id AND l->>'concept_id' = r->>'concept_id'
                            AND (r->>'relationship_type' <> 'prerequisite'
                                OR l->>'support_kind' = 'prerequisite_evidence')))) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_RELATIONSHIP' USING ERRCODE = '22023';
        END IF;
        -- Bounded sink removal, avoiding exponentially many recursive paths.
        -- A -> B means A depends on B. Remove nodes with no remaining dependency.
        SELECT pg_catalog.array_agg(c->>'concept_id') INTO remaining
            FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c;
        SELECT COALESCE(pg_catalog.jsonb_agg(r), '[]'::jsonb) INTO remaining_edges
            FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') r
            WHERE r->>'relationship_type' = 'prerequisite';
        WHILE pg_catalog.cardinality(remaining) > 0 LOOP
            SELECT pg_catalog.array_agg(id) INTO removable FROM pg_catalog.unnest(remaining) n(id)
                WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(remaining_edges) r
                    WHERE r->>'concept_id' = n.id);
            IF removable IS NULL THEN
                RAISE EXCEPTION 'KNOWLEDGE_PREREQUISITE_CYCLE' USING ERRCODE = '22023';
            END IF;
            SELECT COALESCE(pg_catalog.array_agg(id), '{}'::text[]) INTO remaining
                FROM pg_catalog.unnest(remaining) n(id) WHERE NOT id = ANY(removable);
            SELECT COALESCE(pg_catalog.jsonb_agg(r), '[]'::jsonb) INTO remaining_edges
                FROM pg_catalog.jsonb_array_elements(remaining_edges) r
                WHERE NOT (r->>'related_concept_id') = ANY(removable);
        END LOOP;

        INSERT INTO visualai_learning.topics(user_id, source_id, source_version, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'topics')
                x(topic_id text, title text, description text, sequence integer, provenance jsonb);
        INSERT INTO visualai_learning.subtopics(user_id, source_id, source_version, subtopic_id, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.subtopic_id, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'subtopics')
                x(subtopic_id text, topic_id text, title text, description text, sequence integer, provenance jsonb);
        INSERT INTO visualai_learning.concepts(user_id, source_id, source_version, concept_id, name, definition,
            subtopic_id, sequence, provenance, source_content_ids)
            SELECT caller, p_source_id, p_source_version, x.concept_id, x.name, x.definition,
                x.subtopic_id, x.sequence, x.provenance,
                ARRAY(SELECT DISTINCT l->>'content_id'
                    FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                    WHERE l->>'concept_id' = x.concept_id ORDER BY l->>'content_id')
            FROM pg_catalog.jsonb_to_recordset(p_payload->'concepts')
                x(concept_id text, name text, definition text, subtopic_id text, sequence integer, provenance jsonb)
            ON CONFLICT (source_id, source_version, concept_id) DO UPDATE
                SET name = EXCLUDED.name, definition = EXCLUDED.definition, subtopic_id = EXCLUDED.subtopic_id,
                    sequence = EXCLUDED.sequence, provenance = EXCLUDED.provenance,
                    source_content_ids = EXCLUDED.source_content_ids;
        INSERT INTO visualai_learning.content_concepts(user_id, source_id, source_version, content_id, concept_id,
            support_kind, char_start, char_end, extraction_confidence, provenance)
            SELECT caller, p_source_id, p_source_version, x.content_id, x.concept_id, x.support_kind,
                x.char_start, x.char_end, x.extraction_confidence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'content_concepts')
                x(content_id text, concept_id text, support_kind text, char_start integer, char_end integer,
                    extraction_confidence numeric, provenance jsonb);
        INSERT INTO visualai_learning.concept_relationships(user_id, source_id, source_version, concept_id,
            related_concept_id, relationship_type, evidence_content_ids, provenance)
            SELECT caller, p_source_id, p_source_version, x.concept_id, x.related_concept_id,
                x.relationship_type, x.evidence_content_ids, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'relationships')
                x(concept_id text, related_concept_id text, relationship_type text,
                    evidence_content_ids text[], provenance jsonb)
            ON CONFLICT (source_id, source_version, concept_id, related_concept_id, relationship_type)
                DO UPDATE SET evidence_content_ids = EXCLUDED.evidence_content_ids, provenance = EXCLUDED.provenance;
        UPDATE visualai_learning.source_versions SET knowledge_state = 'READY', knowledge_schema_version = 1,
            knowledge_operation_id = p_operation_id, knowledge_payload_hash = payload_hash,
            knowledge_committed_at = pg_catalog.transaction_timestamp(), knowledge_diagnostics = '{}'::jsonb
            WHERE user_id = caller AND source_id = p_source_id AND version = p_source_version
            RETURNING * INTO snapshot;
    END IF;
    RETURN pg_catalog.jsonb_build_object('source_id', snapshot.source_id, 'source_version', snapshot.version,
        'knowledge_state', snapshot.knowledge_state, 'schema_version', snapshot.knowledge_schema_version,
        'operation_id', snapshot.knowledge_operation_id, 'payload_hash', snapshot.knowledge_payload_hash,
        'committed_at', snapshot.knowledge_committed_at);
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.commit_source_ingestion(p_source jsonb, p_version jsonb, p_units jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    caller uuid := visualai_learning_private.owner_id();
    source_key text := p_source->>'source_id';
    version_number integer := (p_source->>'version')::integer;
    existing visualai_learning.sources;
    existing_version visualai_learning.source_versions;
BEGIN
    IF caller IS NULL THEN RAISE EXCEPTION 'Authenticated identity required' USING ERRCODE='42501'; END IF;
    IF jsonb_typeof(p_source) IS DISTINCT FROM 'object'
       OR jsonb_typeof(p_version) IS DISTINCT FROM 'object'
       OR jsonb_typeof(p_units) IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_units)=0 THEN
        RAISE EXCEPTION 'Invalid source aggregate';
    END IF;
    IF p_source->>'user_id' IS DISTINCT FROM caller::text
       OR p_version->>'user_id' IS DISTINCT FROM caller::text
       OR p_version->>'source_id' IS DISTINCT FROM source_key
       OR (p_version->>'version')::integer IS DISTINCT FROM version_number
       OR p_version->>'source_version' IS DISTINCT FROM p_source->>'source_version'
       OR p_version->>'file_hash' IS DISTINCT FROM p_source->>'file_hash'
       OR p_version->>'filename' IS DISTINCT FROM p_source->>'filename'
       OR p_source->>'status' IS DISTINCT FROM 'INDEXING'
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(p_units) u
                  WHERE u->>'user_id' IS DISTINCT FROM caller::text
                     OR u->>'source_id' IS DISTINCT FROM source_key
                     OR (u->>'source_version')::integer IS DISTINCT FROM version_number
                     OR u->>'asset_id' IS DISTINCT FROM p_source->>'asset_id'
                     OR u->>'modality' IS DISTINCT FROM p_source->>'source_type') THEN
        RAISE EXCEPTION 'Invalid owner or provenance' USING ERRCODE='42501';
    END IF;
    IF jsonb_typeof(p_version->'rich_chunks') IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_version->'rich_chunks')=0 THEN
        RAISE EXCEPTION 'Retrieval chunks required';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_version->'rich_chunks') ch
       WHERE ch->>'user_id' IS DISTINCT FROM caller::text
          OR ch->>'source_id' IS DISTINCT FROM source_key
          OR ch->>'asset_id' IS DISTINCT FROM p_source->>'asset_id'
          OR ch->>'source_version' IS DISTINCT FROM p_source->>'source_version'
          OR ch->>'source_type' IS DISTINCT FROM p_source->>'source_type'
          OR jsonb_typeof(ch->'content_ids') IS DISTINCT FROM 'array'
          OR NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_units) u WHERE u->>'content_id'=ch->>'content_id')
          OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(ch->'content_ids') cid
                     WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_units) u WHERE u->>'content_id'=cid))) THEN
        RAISE EXCEPTION 'Invalid chunk provenance';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(source_key, 0));
    SELECT * INTO existing FROM visualai_learning.sources WHERE source_id=source_key FOR UPDATE;
    IF FOUND AND existing.user_id<>caller THEN
        RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501';
    END IF;
    SELECT * INTO existing_version FROM visualai_learning.source_versions
      WHERE source_id=source_key AND version=version_number;
    IF FOUND THEN
        IF existing_version.user_id<>caller
           OR existing_version.file_hash IS DISTINCT FROM p_source->>'file_hash'
           OR existing_version.source_version IS DISTINCT FROM p_source->>'source_version' THEN
            RAISE EXCEPTION 'Immutable source version conflict';
        END IF;
        -- Exact retry returns the original immutable aggregate; it never replaces content.
        RETURN to_jsonb(existing);
    END IF;
    IF existing.source_id IS NOT NULL THEN
        RAISE EXCEPTION 'This ingestion ID already belongs to a different immutable version';
    END IF;
    IF p_source->>'parent_source_id' IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM visualai_learning.sources WHERE source_id=p_source->>'parent_source_id' AND user_id=caller) THEN
       RAISE EXCEPTION 'Parent source unavailable' USING ERRCODE='42501';
    END IF;
    -- Deferred current-version FK is checked at transaction commit after its row exists.
    INSERT INTO visualai_learning.sources (source_id, user_id, legacy_student_id, asset_id, upload_id, filename, source_type, mime_type, file_hash, file_size, version, source_version, title, sha256, parser_version, sanitization_version, parent_source_id, status, error_message) SELECT r.source_id, r.user_id, r.legacy_student_id, r.asset_id, r.upload_id, r.filename, r.source_type, r.mime_type, r.file_hash, r.file_size, r.version, r.source_version, r.title, r.sha256, r.parser_version, r.sanitization_version, r.parent_source_id, r.status, r.error_message FROM pg_catalog.jsonb_populate_record(NULL::visualai_learning.sources, p_source) r;
    INSERT INTO visualai_learning.source_versions (user_id, source_id, version, source_version, file_hash, sha256, filename, file_location, provenance, normalized_content, sanitized_content, quarantined_content, rich_chunks, topic_blueprint) SELECT r.user_id, r.source_id, r.version, r.source_version, r.file_hash, r.sha256, r.filename, r.file_location, r.provenance, r.normalized_content, r.sanitized_content, r.quarantined_content, r.rich_chunks, r.topic_blueprint FROM pg_catalog.jsonb_populate_record(NULL::visualai_learning.source_versions, p_version) r;
    INSERT INTO visualai_learning.content_units (user_id, source_id, source_version, content_id, asset_id, layer, modality, text, visual_description, page_number, page_start, page_end, slide_number, timestamp_start, timestamp_end, speaker, heading_path, frame_id, sequence_index, chapter, section, parent_content_id, char_start, char_end, line_start, line_end, bbox, region_id, image_id, image_path, extraction_method, confidence_score, provenance) SELECT r.user_id, r.source_id, r.source_version, r.content_id, r.asset_id, r.layer, r.modality, r.text, r.visual_description, r.page_number, r.page_start, r.page_end, r.slide_number, r.timestamp_start, r.timestamp_end, r.speaker, r.heading_path, r.frame_id, r.sequence_index, r.chapter, r.section, r.parent_content_id, r.char_start, r.char_end, r.line_start, r.line_end, r.bbox, r.region_id, r.image_id, r.image_path, r.extraction_method, r.confidence_score, r.provenance FROM pg_catalog.jsonb_populate_recordset(NULL::visualai_learning.content_units, p_units) r;
    RETURN (SELECT to_jsonb(s) FROM visualai_learning.sources s WHERE s.source_id=source_key AND s.user_id=caller);
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.extend_validated_snapshot(p_source_id text, p_source_version integer, p_operation_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE
    caller uuid := visualai_learning_private.owner_id();
    snapshot visualai_learning.source_versions;
    payload_hash text;
    item jsonb;
    remaining text[];
    removable text[];
    remaining_edges jsonb;
    -- Initial operational caps, not educational thresholds. See deployment doc.
    max_bytes CONSTANT integer := 2097152;
    max_topics CONSTANT integer := 128;
    max_subtopics CONSTANT integer := 512;
    max_concepts CONSTANT integer := 1024;
    max_links CONSTANT integer := 8192;
    max_edges CONSTANT integer := 4096;
BEGIN
    IF caller IS NULL THEN
        RAISE EXCEPTION 'Authenticated identity required' USING ERRCODE = '42501';
    END IF;
    IF p_source_id IS NULL OR p_source_id !~ '^[A-Za-z0-9_-]{1,128}$'
        OR p_source_version IS NULL OR p_source_version < 1 OR p_operation_id IS NULL
        OR p_payload IS NULL OR pg_catalog.octet_length(p_payload::text) > max_bytes THEN
        RAISE EXCEPTION 'KNOWLEDGE_INVALID_REQUEST' USING ERRCODE = '22023';
    END IF;
    PERFORM visualai_learning_private.knowledge_object(p_payload,
        ARRAY['schema_version','topics','subtopics','concepts','content_concepts','relationships'],
        '{"schema_version":"number","topics":"array","subtopics":"array","concepts":"array","content_concepts":"array","relationships":"array"}');
    IF p_payload->>'schema_version' <> '1'
        OR pg_catalog.jsonb_array_length(p_payload->'topics') NOT BETWEEN 1 AND max_topics
        OR pg_catalog.jsonb_array_length(p_payload->'subtopics') NOT BETWEEN 1 AND max_subtopics
        OR pg_catalog.jsonb_array_length(p_payload->'concepts') NOT BETWEEN 1 AND max_concepts
        OR pg_catalog.jsonb_array_length(p_payload->'content_concepts') NOT BETWEEN 1 AND max_links
        OR pg_catalog.jsonb_array_length(p_payload->'relationships') > max_edges THEN
        RAISE EXCEPTION 'KNOWLEDGE_INVALID_SIZE_OR_VERSION' USING ERRCODE = '22023';
    END IF;
    -- Shape/type validation also applies to idempotent retries.
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'topics') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['topic_id','title','sequence','provenance'],
            '{"topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'subtopics') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['subtopic_id','topic_id','title','sequence','provenance'],
            '{"subtopic_id":"string","topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['concept_id','subtopic_id','name','sequence','provenance'],
            '{"concept_id":"string","subtopic_id":"string","name":"string","definition":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['content_id','concept_id','support_kind','provenance'],
            '{"content_id":"string","concept_id":"string","support_kind":"string","char_start":"number","char_end":"number","extraction_confidence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') LOOP
        PERFORM visualai_learning_private.knowledge_object(item,
            ARRAY['concept_id','related_concept_id','relationship_type','evidence_content_ids','provenance'],
            '{"concept_id":"string","related_concept_id":"string","relationship_type":"string","evidence_content_ids":"array","provenance":"object"}');
        IF pg_catalog.jsonb_array_length(item->'evidence_content_ids') NOT BETWEEN 1 AND 64
            OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(item->'evidence_content_ids') e
                WHERE pg_catalog.jsonb_typeof(e.value) <> 'string') THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_EDGE_EVIDENCE' USING ERRCODE = '22023';
        END IF;
    END LOOP;

    payload_hash := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        visualai_learning_private.knowledge_canonical_json(p_payload)::text, 'UTF8')), 'hex');
    SELECT * INTO snapshot FROM visualai_learning.source_versions
        WHERE user_id = caller AND source_id = p_source_id AND version = p_source_version FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source version unavailable' USING ERRCODE = '42501';
    END IF;
    IF snapshot.knowledge_state = 'READY' THEN
        IF snapshot.knowledge_operation_id IS DISTINCT FROM p_operation_id
            OR snapshot.knowledge_payload_hash IS DISTINCT FROM payload_hash THEN
            RAISE EXCEPTION 'KNOWLEDGE_SNAPSHOT_CONFLICT' USING ERRCODE = '23505';
        END IF;
    ELSE
        -- Every concept is evidenced; every link resolves through this exact canonical scope.
        IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
            WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                WHERE l->>'concept_id' = c->>'concept_id'))
            OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                LEFT JOIN visualai_learning.content_units u ON u.user_id = caller AND u.source_id = p_source_id
                    AND u.source_version = p_source_version AND u.content_id = l->>'content_id'
                WHERE u.content_id IS NULL
                    OR ((l->>'char_start') IS NULL) <> ((l->>'char_end') IS NULL)
                    OR (l->>'char_start')::integer < 0
                    OR (l->>'char_end')::integer <= (l->>'char_start')::integer
                    OR (l->>'char_end')::integer > pg_catalog.char_length(u.text)
                    OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                        WHERE c->>'concept_id' = l->>'concept_id')) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_CONTENT_EVIDENCE' USING ERRCODE = '22023';
        END IF;
        -- A complete mapping must retain every historical concept and relationship.
        IF EXISTS (SELECT 1 FROM visualai_learning.concepts c WHERE c.user_id = caller AND c.source_id = p_source_id
                AND c.source_version = p_source_version AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') n
                    WHERE n->>'concept_id' = c.concept_id))
            OR EXISTS (SELECT 1 FROM visualai_learning.concept_relationships r WHERE r.user_id = caller
                AND r.source_id = p_source_id AND r.source_version = p_source_version AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') n
                    WHERE n->>'concept_id' = r.concept_id AND n->>'related_concept_id' = r.related_concept_id
                        AND n->>'relationship_type' = r.relationship_type)) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INCOMPLETE_LEGACY_MAPPING' USING ERRCODE = '22023';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') r
            WHERE r->>'relationship_type' NOT IN ('prerequisite','related')
                OR r->>'concept_id' = r->>'related_concept_id'
                OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                    WHERE c->>'concept_id' = r->>'concept_id')
                OR NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c
                    WHERE c->>'concept_id' = r->>'related_concept_id')
                OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements_text(r->'evidence_content_ids') e(id)
                    WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                        WHERE l->>'content_id' = e.id AND l->>'concept_id' = r->>'concept_id'
                            AND (r->>'relationship_type' <> 'prerequisite'
                                OR l->>'support_kind' = 'prerequisite_evidence')))) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_RELATIONSHIP' USING ERRCODE = '22023';
        END IF;
        -- Bounded sink removal, avoiding exponentially many recursive paths.
        -- A -> B means A depends on B. Remove nodes with no remaining dependency.
        SELECT pg_catalog.array_agg(c->>'concept_id') INTO remaining
            FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') c;
        SELECT COALESCE(pg_catalog.jsonb_agg(r), '[]'::jsonb) INTO remaining_edges
            FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') r
            WHERE r->>'relationship_type' = 'prerequisite';
        WHILE pg_catalog.cardinality(remaining) > 0 LOOP
            SELECT pg_catalog.array_agg(id) INTO removable FROM pg_catalog.unnest(remaining) n(id)
                WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(remaining_edges) r
                    WHERE r->>'concept_id' = n.id);
            IF removable IS NULL THEN
                RAISE EXCEPTION 'KNOWLEDGE_PREREQUISITE_CYCLE' USING ERRCODE = '22023';
            END IF;
            SELECT COALESCE(pg_catalog.array_agg(id), '{}'::text[]) INTO remaining
                FROM pg_catalog.unnest(remaining) n(id) WHERE NOT id = ANY(removable);
            SELECT COALESCE(pg_catalog.jsonb_agg(r), '[]'::jsonb) INTO remaining_edges
                FROM pg_catalog.jsonb_array_elements(remaining_edges) r
                WHERE NOT (r->>'related_concept_id') = ANY(removable);
        END LOOP;

        INSERT INTO visualai_learning.topics(user_id, source_id, source_version, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'topics')
                x(topic_id text, title text, description text, sequence integer, provenance jsonb)
            ON CONFLICT (user_id,source_id,source_version,topic_id) DO NOTHING;
        INSERT INTO visualai_learning.subtopics(user_id, source_id, source_version, subtopic_id, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.subtopic_id, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'subtopics')
                x(subtopic_id text, topic_id text, title text, description text, sequence integer, provenance jsonb)
            ON CONFLICT (user_id,source_id,source_version,subtopic_id) DO NOTHING;
        INSERT INTO visualai_learning.concepts(user_id, source_id, source_version, concept_id, name, definition,
            subtopic_id, sequence, provenance, source_content_ids)
            SELECT caller, p_source_id, p_source_version, x.concept_id, x.name, x.definition,
                x.subtopic_id, x.sequence, x.provenance,
                ARRAY(SELECT DISTINCT l->>'content_id'
                    FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') l
                    WHERE l->>'concept_id' = x.concept_id ORDER BY l->>'content_id')
            FROM pg_catalog.jsonb_to_recordset(p_payload->'concepts')
                x(concept_id text, name text, definition text, subtopic_id text, sequence integer, provenance jsonb)
            ON CONFLICT (source_id, source_version, concept_id) DO UPDATE
                SET name = EXCLUDED.name, definition = EXCLUDED.definition, subtopic_id = EXCLUDED.subtopic_id,
                    sequence = EXCLUDED.sequence, provenance = EXCLUDED.provenance,
                    source_content_ids = EXCLUDED.source_content_ids;
        INSERT INTO visualai_learning.content_concepts(user_id, source_id, source_version, content_id, concept_id,
            support_kind, char_start, char_end, extraction_confidence, provenance)
            SELECT caller, p_source_id, p_source_version, x.content_id, x.concept_id, x.support_kind,
                x.char_start, x.char_end, x.extraction_confidence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'content_concepts')
                x(content_id text, concept_id text, support_kind text, char_start integer, char_end integer,
                    extraction_confidence numeric, provenance jsonb)
            ON CONFLICT (user_id,source_id,source_version,content_id,concept_id,support_kind) DO NOTHING;
        INSERT INTO visualai_learning.concept_relationships(user_id, source_id, source_version, concept_id,
            related_concept_id, relationship_type, evidence_content_ids, provenance)
            SELECT caller, p_source_id, p_source_version, x.concept_id, x.related_concept_id,
                x.relationship_type, x.evidence_content_ids, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'relationships')
                x(concept_id text, related_concept_id text, relationship_type text,
                    evidence_content_ids text[], provenance jsonb)
            ON CONFLICT (source_id, source_version, concept_id, related_concept_id, relationship_type)
                DO UPDATE SET evidence_content_ids = EXCLUDED.evidence_content_ids, provenance = EXCLUDED.provenance;
        UPDATE visualai_learning.source_versions SET knowledge_state = 'READY', knowledge_schema_version = 1,
            knowledge_operation_id = p_operation_id, knowledge_payload_hash = payload_hash,
            knowledge_committed_at = pg_catalog.transaction_timestamp(), knowledge_diagnostics = '{}'::jsonb
            WHERE user_id = caller AND source_id = p_source_id AND version = p_source_version
            RETURNING * INTO snapshot;
    END IF;
    RETURN pg_catalog.jsonb_build_object('source_id', snapshot.source_id, 'source_version', snapshot.version,
        'knowledge_state', snapshot.knowledge_state, 'schema_version', snapshot.knowledge_schema_version,
        'operation_id', snapshot.knowledge_operation_id, 'payload_hash', snapshot.knowledge_payload_hash,
        'committed_at', snapshot.knowledge_committed_at);
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.knowledge_canonical_json(p_value jsonb, p_depth integer DEFAULT 0)
 RETURNS jsonb
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
DECLARE result jsonb;
BEGIN
    IF p_depth > 16 THEN
        RAISE EXCEPTION 'KNOWLEDGE_JSON_TOO_DEEP' USING ERRCODE = '22023';
    END IF;
    CASE pg_catalog.jsonb_typeof(p_value)
    WHEN 'number' THEN
        RETURN pg_catalog.to_jsonb(pg_catalog.trim_scale((p_value #>> '{}')::numeric));
    WHEN 'array' THEN
        SELECT COALESCE(pg_catalog.jsonb_agg(
            visualai_learning_private.knowledge_canonical_json(e.value, p_depth + 1) ORDER BY e.ordinality), '[]'::jsonb)
            INTO result FROM pg_catalog.jsonb_array_elements(p_value) WITH ORDINALITY e;
    WHEN 'object' THEN
        SELECT COALESCE(pg_catalog.jsonb_object_agg(e.key,
            visualai_learning_private.knowledge_canonical_json(e.value, p_depth + 1)), '{}'::jsonb)
            INTO result FROM pg_catalog.jsonb_each(p_value) e;
    ELSE RETURN p_value;
    END CASE;
    RETURN result;
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.knowledge_object(p_value jsonb, p_required text[], p_types jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE k text; v jsonb; expected text;
BEGIN
    IF pg_catalog.jsonb_typeof(p_value) IS DISTINCT FROM 'object'
        OR NOT p_value ?& p_required THEN
        RAISE EXCEPTION 'KNOWLEDGE_INVALID_OBJECT' USING ERRCODE = '22023';
    END IF;
    FOR k, v IN SELECT * FROM pg_catalog.jsonb_each(p_value) LOOP
        expected := p_types->>k;
        IF expected IS NULL THEN
            RAISE EXCEPTION 'KNOWLEDGE_UNKNOWN_FIELD: %', k USING ERRCODE = '22023';
        END IF;
        IF v = 'null'::jsonb AND k = ANY(ARRAY[
            'description','definition','char_start','char_end','extraction_confidence']) THEN
            CONTINUE;
        END IF;
        IF pg_catalog.jsonb_typeof(v) IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_TYPE: %', k USING ERRCODE = '22023';
        END IF;
        IF expected = 'string' AND (pg_catalog.length(v #>> '{}') > 16384
            OR (k NOT IN ('description','definition') AND pg_catalog.btrim(v #>> '{}') = '')) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_TEXT: %', k USING ERRCODE = '22023';
        END IF;
        IF k IN ('topic_id','subtopic_id','concept_id','related_concept_id','content_id')
            AND (v #>> '{}') !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$' THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_ID: %', k USING ERRCODE = '22023';
        END IF;
        IF k IN ('sequence','char_start','char_end','schema_version')
            AND ((v #>> '{}') !~ '^(0|[1-9][0-9]{0,9})$'
                OR (v #>> '{}')::numeric > 2147483647) THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_INTEGER: %', k USING ERRCODE = '22023';
        END IF;
        IF k = 'extraction_confidence' AND (v #>> '{}')::numeric NOT BETWEEN 0 AND 1 THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_CONFIDENCE' USING ERRCODE = '22023';
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.learning_transaction(p_action text, p_user_id uuid, p_learning_session_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    learning visualai_learning.learning_sessions;
    assessment visualai_learning.assessment_sessions;
    job visualai_learning.remediation_jobs;
    item jsonb;
    target_table text;
    evidence_id text;
BEGIN
    IF p_user_id IS DISTINCT FROM visualai_learning_private.owner_id() THEN
        RAISE EXCEPTION 'Owner unavailable' USING ERRCODE='42501';
    END IF;
    IF p_action IS NULL OR p_action NOT IN ('load','finalize','complete') OR p_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid learning operation' USING ERRCODE='22023';
    END IF;
    SELECT * INTO learning FROM visualai_learning.learning_sessions WHERE session_id=p_learning_session_id AND user_id=p_user_id FOR UPDATE;
    IF learning.session_id IS NULL THEN RETURN NULL; END IF;
    IF p_action<>'load' THEN
        IF learning.state<>'ACTIVE' OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023';
        END IF;
        IF p_action='finalize' THEN
            SELECT * INTO assessment FROM visualai_learning.assessment_sessions WHERE session_id=p_payload->>'assessment_id'
                AND user_id=p_user_id AND learning_session_id=p_learning_session_id
                AND source_id=learning.source_id AND source_version=learning.source_version FOR UPDATE;
            IF assessment.session_id IS NULL OR assessment.status<>'SUBMITTED' THEN RETURN NULL; END IF;
            IF assessment.mastery_applied_at IS NOT NULL THEN
                RETURN visualai_learning_private.learning_transaction('load',p_user_id,p_learning_session_id,'{}');
            END IF;
            IF EXISTS(SELECT 1 FROM visualai_learning.assessment_sessions a WHERE a.user_id=p_user_id
                AND a.learning_session_id=p_learning_session_id AND a.status='SUBMITTED' AND a.mastery_applied_at IS NULL
                AND (a.submitted_at,a.session_id)<(assessment.submitted_at,assessment.session_id)) THEN
                RAISE EXCEPTION 'Earlier assessment pending' USING ERRCODE='23505';
            END IF;
        ELSE
            SELECT * INTO job FROM visualai_learning.remediation_jobs WHERE remediation_job_id=p_payload->>'job_id'
                AND user_id=p_user_id AND learning_session_id=p_learning_session_id FOR UPDATE;
            IF job.remediation_job_id IS NULL THEN RETURN NULL; END IF;
            IF job.metadata->>'completed'='true' THEN
                RETURN visualai_learning_private.learning_transaction('load',p_user_id,p_learning_session_id,'{}');
            END IF;
            IF job.status<>'READY' OR NOT EXISTS(SELECT 1 FROM visualai_learning.concept_mastery m
                WHERE m.user_id=p_user_id AND m.learning_session_id=p_learning_session_id AND m.concept_id=job.concept_id
                AND m.mastery_state='REMEDIATING' AND m.remediation_attempt_count=job.attempt_number) THEN
                RAISE EXCEPTION 'Remediation unavailable' USING ERRCODE='22023';
            END IF;
        END IF;
        IF (p_payload->>'expected_revision')::integer IS DISTINCT FROM learning.mastery_revision THEN
            RAISE EXCEPTION 'Learning revision conflict' USING ERRCODE='23505';
        END IF;
        FOREACH target_table IN ARRAY ARRAY['mastery','gaps','remediation'] LOOP
            IF jsonb_typeof(p_payload->target_table) IS DISTINCT FROM 'array' OR jsonb_array_length(p_payload->target_table)>1024 THEN
                RAISE EXCEPTION 'Invalid learning payload' USING ERRCODE='22023';
            END IF;
            FOR item IN SELECT value FROM jsonb_array_elements(p_payload->target_table) LOOP
                IF item->>'user_id' IS DISTINCT FROM p_user_id::text
                   OR item->>'learning_session_id' IS DISTINCT FROM p_learning_session_id::text
                   OR item->>'source_id' IS DISTINCT FROM learning.source_id
                   OR (item->>'source_version')::integer IS DISTINCT FROM learning.source_version
                   OR NOT EXISTS(SELECT 1 FROM visualai_learning.concepts c WHERE c.user_id=p_user_id AND c.source_id=learning.source_id
                        AND c.source_version=learning.source_version AND c.concept_id=item->>'concept_id') THEN
                    RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023';
                END IF;
                FOR evidence_id IN SELECT jsonb_array_elements_text(coalesce(item->'evidence_attempt_ids',item->'processed_attempt_ids','[]')) LOOP
                    IF NOT EXISTS(SELECT 1 FROM visualai_learning.assessment_attempts a JOIN visualai_learning.assessment_sessions s
                        ON s.session_id=a.session_id AND s.user_id=a.user_id WHERE a.attempt_id=evidence_id
                        AND a.user_id=p_user_id AND s.learning_session_id=p_learning_session_id AND a.concept_id=item->>'concept_id') THEN
                        RAISE EXCEPTION 'Learning evidence unavailable' USING ERRCODE='22023';
                    END IF;
                END LOOP;
            END LOOP;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'mastery') LOOP
            INSERT INTO visualai_learning.concept_mastery(user_id,source_id,source_version,concept_id,session_id,attempt_count,correct_count,incorrect_count,reassessment_attempt_count,reassessment_correct_count,lifetime_accuracy,mastery_score,mastery_state,remediation_attempt_count,processed_attempt_ids,last_assessed_at,last_remediation_at,created_at,updated_at,learning_session_id,consecutive_correct)
            SELECT user_id,source_id,source_version,concept_id,session_id,attempt_count,correct_count,incorrect_count,reassessment_attempt_count,reassessment_correct_count,lifetime_accuracy,mastery_score,mastery_state,remediation_attempt_count,processed_attempt_ids,last_assessed_at,last_remediation_at,created_at,updated_at,learning_session_id,consecutive_correct FROM jsonb_populate_record(NULL::visualai_learning.concept_mastery,item)
            ON CONFLICT (user_id,source_id,source_version,learning_session_id,concept_id) WHERE learning_session_id IS NOT NULL DO UPDATE SET session_id=EXCLUDED.session_id,attempt_count=EXCLUDED.attempt_count,correct_count=EXCLUDED.correct_count,incorrect_count=EXCLUDED.incorrect_count,reassessment_attempt_count=EXCLUDED.reassessment_attempt_count,reassessment_correct_count=EXCLUDED.reassessment_correct_count,lifetime_accuracy=EXCLUDED.lifetime_accuracy,mastery_score=EXCLUDED.mastery_score,mastery_state=EXCLUDED.mastery_state,remediation_attempt_count=EXCLUDED.remediation_attempt_count,processed_attempt_ids=EXCLUDED.processed_attempt_ids,last_assessed_at=EXCLUDED.last_assessed_at,last_remediation_at=EXCLUDED.last_remediation_at,updated_at=EXCLUDED.updated_at,consecutive_correct=EXCLUDED.consecutive_correct;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'gaps') LOOP
            INSERT INTO visualai_learning.misconceptions(misconception_id,user_id,source_id,source_version,session_id,concept_id,misconception_code,misconception_label,misconception_description,misconception_type,evidence_question_ids,evidence_attempt_ids,occurrence_count,confidence_state,status,first_detected_at,last_detected_at,corrected_at,source_chunk_ids,supporting_evidence_summary,learning_session_id)
            SELECT misconception_id,user_id,source_id,source_version,session_id,concept_id,misconception_code,misconception_label,misconception_description,misconception_type,evidence_question_ids,evidence_attempt_ids,occurrence_count,confidence_state,status,first_detected_at,last_detected_at,corrected_at,source_chunk_ids,supporting_evidence_summary,learning_session_id FROM jsonb_populate_record(NULL::visualai_learning.misconceptions,item)
            ON CONFLICT (misconception_id) DO UPDATE SET session_id=EXCLUDED.session_id,concept_id=EXCLUDED.concept_id,misconception_code=EXCLUDED.misconception_code,misconception_label=EXCLUDED.misconception_label,misconception_description=EXCLUDED.misconception_description,misconception_type=EXCLUDED.misconception_type,evidence_question_ids=EXCLUDED.evidence_question_ids,evidence_attempt_ids=EXCLUDED.evidence_attempt_ids,occurrence_count=EXCLUDED.occurrence_count,confidence_state=EXCLUDED.confidence_state,status=EXCLUDED.status,first_detected_at=EXCLUDED.first_detected_at,last_detected_at=EXCLUDED.last_detected_at,corrected_at=EXCLUDED.corrected_at,source_chunk_ids=EXCLUDED.source_chunk_ids,supporting_evidence_summary=EXCLUDED.supporting_evidence_summary WHERE misconceptions.user_id=p_user_id AND misconceptions.learning_session_id=p_learning_session_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'remediation') LOOP
            INSERT INTO visualai_learning.remediation_jobs(remediation_job_id,user_id,source_id,source_version,session_id,concept_id,status,video_job_id,video_path,duration_seconds,attempt_number,idempotency_key,strategy_used,misconception_code,evidence_attempt_ids,started_at,completed_at,failed_at,failure_code,failure_message,is_infrastructure_failure,metadata,created_at,updated_at,learning_session_id)
            SELECT remediation_job_id,user_id,source_id,source_version,session_id,concept_id,status,video_job_id,video_path,duration_seconds,attempt_number,idempotency_key,strategy_used,misconception_code,evidence_attempt_ids,started_at,completed_at,failed_at,failure_code,failure_message,is_infrastructure_failure,metadata,created_at,updated_at,learning_session_id FROM jsonb_populate_record(NULL::visualai_learning.remediation_jobs,item||jsonb_build_object('updated_at',clock_timestamp()))
            ON CONFLICT (remediation_job_id) DO UPDATE SET session_id=EXCLUDED.session_id,concept_id=EXCLUDED.concept_id,status=EXCLUDED.status,video_job_id=EXCLUDED.video_job_id,video_path=EXCLUDED.video_path,duration_seconds=EXCLUDED.duration_seconds,attempt_number=EXCLUDED.attempt_number,idempotency_key=EXCLUDED.idempotency_key,strategy_used=EXCLUDED.strategy_used,misconception_code=EXCLUDED.misconception_code,evidence_attempt_ids=EXCLUDED.evidence_attempt_ids,started_at=EXCLUDED.started_at,completed_at=EXCLUDED.completed_at,failed_at=EXCLUDED.failed_at,failure_code=EXCLUDED.failure_code,failure_message=EXCLUDED.failure_message,is_infrastructure_failure=EXCLUDED.is_infrastructure_failure,metadata=EXCLUDED.metadata,updated_at=EXCLUDED.updated_at WHERE remediation_jobs.user_id=p_user_id AND remediation_jobs.learning_session_id=p_learning_session_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        IF p_action='finalize' THEN
            UPDATE visualai_learning.assessment_sessions SET mastery_applied_at=clock_timestamp()
                WHERE session_id=assessment.session_id AND user_id=p_user_id;
        END IF;
        UPDATE visualai_learning.learning_sessions SET mastery_revision=mastery_revision+1 WHERE session_id=p_learning_session_id AND user_id=p_user_id;
    END IF;
    RETURN jsonb_build_object('revision',(SELECT mastery_revision FROM visualai_learning.learning_sessions WHERE session_id=p_learning_session_id AND user_id=p_user_id),
        'mastery',(SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY concept_id),'[]') FROM visualai_learning.concept_mastery m WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'gaps',(SELECT coalesce(jsonb_agg(to_jsonb(g) ORDER BY concept_id),'[]') FROM visualai_learning.misconceptions g WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'remediation',(SELECT coalesce(jsonb_agg(to_jsonb(j) ORDER BY created_at,remediation_job_id),'[]') FROM visualai_learning.remediation_jobs j WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'attempts',(SELECT coalesce(jsonb_agg(to_jsonb(a)||jsonb_build_object('learning_session_id',s.learning_session_id) ORDER BY a.submitted_at,a.attempt_id),'[]')
            FROM visualai_learning.assessment_attempts a JOIN visualai_learning.assessment_sessions s ON s.session_id=a.session_id AND s.user_id=a.user_id
            WHERE a.user_id=p_user_id AND s.learning_session_id=p_learning_session_id AND a.source_id=learning.source_id AND a.source_version=learning.source_version),
        'applied_assessments',(SELECT coalesce(jsonb_agg(session_id ORDER BY submitted_at,session_id),'[]') FROM visualai_learning.assessment_sessions
            WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id AND mastery_applied_at IS NOT NULL));
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.mutate_learning_session(p_action text, p_session_id uuid, p_source_id text DEFAULT NULL::text, p_source_version integer DEFAULT NULL::integer, p_topic_id text DEFAULT NULL::text, p_subtopic_id text DEFAULT NULL::text, p_concept_ids text[] DEFAULT NULL::text[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    owner_id uuid := visualai_learning_private.owner_id();
    existing visualai_learning.learning_sessions;
    resolved text[];
    instant timestamptz := clock_timestamp();
BEGIN
    IF owner_id IS NULL OR p_session_id IS NULL THEN
        RAISE EXCEPTION 'Session unavailable' USING ERRCODE='42501';
    END IF;
    IF p_action NOT IN ('create','selection','resume','complete','abandon') OR p_action IS NULL THEN
        RAISE EXCEPTION 'Invalid session operation' USING ERRCODE='22023';
    END IF;
    -- Serialize create/retry/transition for this UUID, including the absent-row case.
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_session_id::text, 0));
    SELECT * INTO existing FROM visualai_learning.learning_sessions
        WHERE session_id=p_session_id AND user_id=owner_id FOR UPDATE;
    IF p_action <> 'create' AND existing.session_id IS NULL THEN
        RAISE EXCEPTION 'Session unavailable' USING ERRCODE='42501';
    END IF;
    IF p_action IN ('create','selection') THEN
        IF p_action='selection' THEN
            IF existing.state <> 'ACTIVE' THEN
                RAISE EXCEPTION 'Session is not active' USING ERRCODE='55000';
            END IF;
            IF p_source_id IS DISTINCT FROM existing.source_id
                OR p_source_version IS DISTINCT FROM existing.source_version THEN
                RAISE EXCEPTION 'Pinned source cannot change' USING ERRCODE='22023';
            END IF;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM visualai_learning.source_versions
            WHERE user_id=owner_id AND source_id=p_source_id AND version=p_source_version
                AND knowledge_state='READY') OR NOT EXISTS (SELECT 1 FROM visualai_learning.topics
            WHERE user_id=owner_id AND source_id=p_source_id AND source_version=p_source_version
                AND topic_id=p_topic_id) OR (p_subtopic_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM visualai_learning.subtopics WHERE user_id=owner_id AND source_id=p_source_id
                AND source_version=p_source_version AND topic_id=p_topic_id AND subtopic_id=p_subtopic_id)) THEN
            RAISE EXCEPTION 'Selection unavailable' USING ERRCODE='42501';
        END IF;
        SELECT array_agg(c.concept_id ORDER BY c.concept_id) INTO resolved
            FROM visualai_learning.concepts c JOIN visualai_learning.subtopics s
            ON (s.user_id,s.source_id,s.source_version,s.subtopic_id)=
               (c.user_id,c.source_id,c.source_version,c.subtopic_id)
            WHERE c.user_id=owner_id AND c.source_id=p_source_id AND c.source_version=p_source_version
                AND s.topic_id=p_topic_id AND (p_subtopic_id IS NULL OR c.subtopic_id=p_subtopic_id);
        IF resolved IS NULL OR cardinality(resolved)>64 OR p_concept_ids IS DISTINCT FROM resolved THEN
            RAISE EXCEPTION 'Selection unavailable' USING ERRCODE='42501';
        END IF;
        IF p_action='create' THEN
            IF existing.session_id IS NOT NULL THEN
                IF (existing.source_id,existing.source_version,existing.topic_id) IS DISTINCT FROM
                   (p_source_id,p_source_version,p_topic_id) OR existing.subtopic_id IS DISTINCT FROM p_subtopic_id
                   OR existing.selected_concept_ids IS DISTINCT FROM resolved THEN
                    RAISE EXCEPTION 'Session conflict' USING ERRCODE='23505';
                END IF;
                RETURN to_jsonb(existing);
            END IF;
            IF EXISTS (SELECT 1 FROM visualai_learning.learning_sessions WHERE session_id=p_session_id) THEN
                RAISE EXCEPTION 'Session unavailable' USING ERRCODE='42501';
            END IF;
            INSERT INTO visualai_learning.learning_sessions(session_id,user_id,source_id,source_version,topic_id,subtopic_id,selected_concept_ids)
                VALUES(p_session_id,owner_id,p_source_id,p_source_version,p_topic_id,p_subtopic_id,resolved)
                RETURNING * INTO existing;
        ELSE
            UPDATE visualai_learning.learning_sessions SET topic_id=p_topic_id,subtopic_id=p_subtopic_id,
                selected_concept_ids=resolved,updated_at=instant,last_active_at=instant
                WHERE session_id=p_session_id AND user_id=owner_id RETURNING * INTO existing;
        END IF;
    ELSE
        IF p_source_id IS NOT NULL OR p_source_version IS NOT NULL OR p_topic_id IS NOT NULL
            OR p_subtopic_id IS NOT NULL OR p_concept_ids IS NOT NULL THEN
            RAISE EXCEPTION 'Unexpected selection' USING ERRCODE='22023';
        END IF;
        IF existing.state <> 'ACTIVE' THEN
            IF (p_action='complete' AND existing.state='COMPLETED') OR
                (p_action='abandon' AND existing.state='ABANDONED') THEN RETURN to_jsonb(existing); END IF;
            RAISE EXCEPTION 'Session is not active' USING ERRCODE='55000';
        END IF;
        UPDATE visualai_learning.learning_sessions SET
            state=CASE p_action WHEN 'complete' THEN 'COMPLETED' WHEN 'abandon' THEN 'ABANDONED' ELSE 'ACTIVE' END,
            updated_at=instant,last_active_at=instant
            WHERE session_id=p_session_id AND user_id=owner_id RETURNING * INTO existing;
    END IF;
    RETURN to_jsonb(existing);
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.rebuild_verified_knowledge(p_source_id text, p_source_version integer, p_expected_hash text, p_operation_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE caller uuid := (SELECT visualai_learning_private.owner_id()); previous visualai_learning.source_versions; result jsonb;
BEGIN
    IF caller IS NULL THEN RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501'; END IF;
    SELECT * INTO previous FROM visualai_learning.source_versions WHERE user_id=caller
        AND source_id=p_source_id AND version=p_source_version FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501'; END IF;
    IF previous.knowledge_operation_id=p_operation_id THEN
        RETURN visualai_learning_private.extend_validated_snapshot(p_source_id,p_source_version,p_operation_id,p_payload);
    END IF;
    IF previous.knowledge_state<>'READY' OR previous.knowledge_payload_hash IS DISTINCT FROM p_expected_hash THEN
        RAISE EXCEPTION 'Knowledge revision conflict' USING ERRCODE='23505';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM visualai_learning.content_units WHERE user_id=caller AND source_id=p_source_id AND source_version=p_source_version)
       OR EXISTS(SELECT 1 FROM visualai_learning.content_units u WHERE u.user_id=caller AND u.source_id=p_source_id
        AND u.source_version=p_source_version AND (u.provenance->>'visual_schema_version' IS DISTINCT FROM 'visual-v2'
            OR u.provenance->'visual_verification'->>'status' IS DISTINCT FROM 'VERIFIED')) THEN
        RAISE EXCEPTION 'Verified extraction unavailable' USING ERRCODE='22023';
    END IF;
    IF EXISTS(SELECT 1 FROM visualai_learning.topics r WHERE r.user_id=caller AND r.source_id=p_source_id AND r.source_version=p_source_version AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'topics') n WHERE jsonb_strip_nulls(n)=jsonb_strip_nulls(jsonb_build_object('topic_id',r.topic_id,'title',r.title,'description',r.description,'sequence',r.sequence,'provenance',r.provenance)))) OR
       EXISTS(SELECT 1 FROM visualai_learning.subtopics r WHERE r.user_id=caller AND r.source_id=p_source_id AND r.source_version=p_source_version AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'subtopics') n WHERE jsonb_strip_nulls(n)=jsonb_strip_nulls(jsonb_build_object('subtopic_id',r.subtopic_id,'topic_id',r.topic_id,'title',r.title,'description',r.description,'sequence',r.sequence,'provenance',r.provenance)))) OR
       EXISTS(SELECT 1 FROM visualai_learning.concepts r WHERE r.user_id=caller AND r.source_id=p_source_id AND r.source_version=p_source_version AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'concepts') n WHERE jsonb_strip_nulls(n)=jsonb_strip_nulls(jsonb_build_object('concept_id',r.concept_id,'subtopic_id',r.subtopic_id,'name',r.name,'definition',r.definition,'sequence',r.sequence,'provenance',r.provenance)))) OR
       EXISTS(SELECT 1 FROM visualai_learning.content_concepts r WHERE r.user_id=caller AND r.source_id=p_source_id AND r.source_version=p_source_version AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'content_concepts') n WHERE jsonb_strip_nulls(n)=jsonb_strip_nulls(jsonb_build_object('content_id',r.content_id,'concept_id',r.concept_id,'support_kind',r.support_kind,'char_start',r.char_start,'char_end',r.char_end,'extraction_confidence',r.extraction_confidence,'provenance',r.provenance)))) OR
       EXISTS(SELECT 1 FROM visualai_learning.concept_relationships r WHERE r.user_id=caller AND r.source_id=p_source_id AND r.source_version=p_source_version AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'relationships') n WHERE jsonb_strip_nulls(n)=jsonb_strip_nulls(jsonb_build_object('concept_id',r.concept_id,'related_concept_id',r.related_concept_id,'relationship_type',r.relationship_type,'evidence_content_ids',r.evidence_content_ids,'provenance',r.provenance)))) THEN
        RAISE EXCEPTION 'Historical knowledge must remain unchanged' USING ERRCODE='22023';
    END IF;
    UPDATE visualai_learning.source_versions SET knowledge_state='PENDING',knowledge_schema_version=NULL,knowledge_operation_id=NULL,
        knowledge_payload_hash=NULL,knowledge_committed_at=NULL WHERE user_id=caller AND source_id=p_source_id AND version=p_source_version;
    result := visualai_learning_private.extend_validated_snapshot(p_source_id,p_source_version,p_operation_id,p_payload);
    UPDATE visualai_learning.source_versions SET knowledge_diagnostics=jsonb_build_object('rebuild_policy','verified-hierarchy-extension-v1','rebuild_history',
        coalesce(previous.knowledge_diagnostics->'rebuild_history','[]'::jsonb)||jsonb_build_array(jsonb_build_object(
            'operation_id',previous.knowledge_operation_id,'payload_hash',previous.knowledge_payload_hash,
            'committed_at',previous.knowledge_committed_at))) WHERE user_id=caller AND source_id=p_source_id AND version=p_source_version;
    RETURN result;
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.remediation_video(p_user_id uuid, p_learning_session_id uuid, p_remediation_id text, p_action text, p_payload jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    learning visualai_learning.learning_sessions;
    job visualai_learning.remediation_jobs;
    video visualai_learning.generated_videos;
    claimed boolean := false;
BEGIN
    IF p_user_id IS DISTINCT FROM visualai_learning_private.owner_id() THEN
        RAISE EXCEPTION 'Owner unavailable' USING ERRCODE='42501';
    END IF;
    IF p_user_id IS DISTINCT FROM visualai_learning_private.owner_id() THEN
        RAISE EXCEPTION 'Video unavailable' USING ERRCODE='42501';
    END IF;
    IF p_action NOT IN ('get','claim','save') OR p_action IS NULL
        OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object'
        OR pg_column_size(p_payload)>2097152 THEN
        RAISE EXCEPTION 'Invalid video operation' USING ERRCODE='22023';
    END IF;
    SELECT * INTO learning FROM visualai_learning.learning_sessions
        WHERE user_id=p_user_id AND session_id=p_learning_session_id FOR UPDATE;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO job FROM visualai_learning.remediation_jobs WHERE user_id=p_user_id
        AND learning_session_id=p_learning_session_id AND remediation_job_id=p_remediation_id
        AND source_id=learning.source_id AND source_version=learning.source_version FOR UPDATE;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO video FROM visualai_learning.generated_videos WHERE user_id=p_user_id
        AND source_id=job.source_id AND source_version=job.source_version
        AND concept_id=job.concept_id AND job_id=job.video_job_id FOR UPDATE;
    IF p_action='claim' AND video.job_id IS NULL THEN
        IF learning.state<>'ACTIVE' OR job.metadata->>'completed' IS DISTINCT FROM 'false'
            OR job.status<>'READY' OR NOT EXISTS(SELECT 1 FROM visualai_learning.concept_mastery m
                WHERE m.user_id=p_user_id AND m.learning_session_id=p_learning_session_id
                AND m.concept_id=job.concept_id AND m.mastery_state='REMEDIATING'
                AND m.remediation_attempt_count=job.attempt_number) THEN
            RAISE EXCEPTION 'Video unavailable' USING ERRCODE='23505';
        END IF;
        INSERT INTO visualai_learning.generated_videos(job_id,user_id,source_id,source_version,concept_id,concept_name,plan,output_metadata)
        VALUES('VIDEO_'||gen_random_uuid()::text,p_user_id,job.source_id,job.source_version,job.concept_id,
            (SELECT name FROM visualai_learning.concepts WHERE user_id=p_user_id AND source_id=job.source_id
                AND source_version=job.source_version AND concept_id=job.concept_id),p_payload->'plan',
            jsonb_build_object('learning_session_id',p_learning_session_id,'remediation_job_id',p_remediation_id,
                'attempt_number',job.attempt_number)) RETURNING * INTO video;
        UPDATE visualai_learning.remediation_jobs SET video_job_id=video.job_id
            WHERE remediation_job_id=p_remediation_id AND user_id=p_user_id;
        UPDATE visualai_learning.learning_sessions SET mastery_revision=mastery_revision+1
            WHERE session_id=p_learning_session_id AND user_id=p_user_id;
        claimed := true;
    ELSIF p_action='save' THEN
        IF video.job_id IS NULL OR video.job_id IS DISTINCT FROM p_payload->>'job_id'
            OR video.status IN ('COMPLETED','FAILED') THEN
            RAISE EXCEPTION 'Video unavailable' USING ERRCODE='23505';
        END IF;
        UPDATE visualai_learning.generated_videos SET status=p_payload->>'status',stage=p_payload->>'stage',
            progress=(p_payload->>'progress')::integer,duration_seconds=(p_payload->>'duration_seconds')::double precision,
            video_path=p_payload->>'video_path',audio_path=p_payload->>'audio_path',subtitle_path=p_payload->>'subtitle_path',
            error=CASE WHEN p_payload->>'status'='FAILED' THEN 'VIDEO_RENDER_FAILED' ELSE NULL END,
            completed_at=(p_payload->>'completed_at')::timestamptz
            WHERE job_id=video.job_id AND user_id=p_user_id RETURNING * INTO video;
    END IF;
    IF video.job_id IS NULL THEN RETURN NULL; END IF;
    RETURN jsonb_build_object('claimed',claimed,'video',to_jsonb(video));
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.source_index_status(p_source_id text, p_version integer, p_status text, p_error text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    caller uuid := visualai_learning_private.owner_id();
    result jsonb;
BEGIN
    IF caller IS NULL THEN RAISE EXCEPTION 'Authenticated identity required' USING ERRCODE='42501'; END IF;
    IF p_status IS NULL OR p_status NOT IN ('INDEXING','READY','FAILED')
       OR (p_status='FAILED' AND coalesce(p_error,'')='') THEN
        RAISE EXCEPTION 'Invalid indexing status';
    END IF;
    UPDATE visualai_learning.sources s SET status=p_status, error_message=CASE WHEN p_status='FAILED' THEN p_error ELSE NULL END
      WHERE s.source_id=p_source_id AND s.user_id=caller AND s.version=p_version
      AND EXISTS (SELECT 1 FROM visualai_learning.source_versions v WHERE v.source_id=s.source_id AND v.user_id=caller AND v.version=p_version)
      RETURNING to_jsonb(s) INTO result;
    IF result IS NULL THEN RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501'; END IF;
    RETURN result;
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning_private.validate_remediation_video_completion()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
BEGIN
    IF NEW.learning_session_id IS NOT NULL AND NEW.video_job_id IS NOT NULL
        AND NEW.metadata->>'completed'='true' AND OLD.metadata->>'completed' IS DISTINCT FROM 'true'
        AND NOT EXISTS(SELECT 1 FROM visualai_learning.generated_videos v WHERE v.job_id=NEW.video_job_id
            AND v.user_id=NEW.user_id AND v.source_id=NEW.source_id AND v.source_version=NEW.source_version
            AND v.concept_id=NEW.concept_id AND v.status='COMPLETED'
            AND v.output_metadata->>'learning_session_id'=NEW.learning_session_id::text
            AND v.output_metadata->>'remediation_job_id'=NEW.remediation_job_id) THEN
        RAISE EXCEPTION 'Video not ready' USING ERRCODE='23505';
    END IF;
    RETURN NEW;
END $function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_assessment_transaction(p_action text, p_user_id uuid, p_assessment_id text, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.assessment_transaction(p_action,p_user_id,p_assessment_id,p_payload)
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_commit_knowledge_snapshot(p_source_id text, p_source_version integer, p_operation_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.commit_knowledge_snapshot(p_source_id, p_source_version, p_operation_id, p_payload);
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_commit_source_ingestion(p_source jsonb, p_version jsonb, p_units jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.commit_source_ingestion(p_source, p_version, p_units);
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_learning_transaction(p_action text, p_user_id uuid, p_learning_session_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.learning_transaction(p_action,p_user_id,p_learning_session_id,p_payload)
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_mutate_learning_session(p_action text, p_session_id uuid, p_source_id text DEFAULT NULL::text, p_source_version integer DEFAULT NULL::integer, p_topic_id text DEFAULT NULL::text, p_subtopic_id text DEFAULT NULL::text, p_concept_ids text[] DEFAULT NULL::text[])
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.mutate_learning_session(p_action,p_session_id,p_source_id,p_source_version,p_topic_id,p_subtopic_id,p_concept_ids)
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_rebuild_verified_knowledge(p_source_id text, p_source_version integer, p_expected_hash text, p_operation_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.rebuild_verified_knowledge(p_source_id,p_source_version,p_expected_hash,p_operation_id,p_payload)
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_remediation_video(p_user_id uuid, p_learning_session_id uuid, p_remediation_id text, p_action text, p_payload jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.remediation_video(p_user_id,p_learning_session_id,p_remediation_id,p_action,p_payload)
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION visualai_learning.visualai_source_index_status(p_source_id text, p_version integer, p_status text, p_error text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$
    SELECT visualai_learning_private.source_index_status(p_source_id,p_version,p_status,p_error);
$function$;
ALTER TABLE visualai_learning.assessment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.assessment_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.assessment_attempts
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.assessment_attempts FROM PUBLIC;
CREATE TRIGGER assessment_questions_set_updated_at BEFORE UPDATE ON visualai_learning.assessment_questions FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.assessment_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.assessment_questions FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.assessment_questions
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.assessment_questions FROM PUBLIC;
CREATE TRIGGER assessment_sessions_set_updated_at BEFORE UPDATE ON visualai_learning.assessment_sessions FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.assessment_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.assessment_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.assessment_sessions
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.assessment_sessions FROM PUBLIC;
CREATE TRIGGER concept_mastery_set_updated_at BEFORE UPDATE ON visualai_learning.concept_mastery FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.concept_mastery ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.concept_mastery FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.concept_mastery
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.concept_mastery FROM PUBLIC;
ALTER TABLE visualai_learning.concept_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.concept_relationships FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.concept_relationships
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.concept_relationships FROM PUBLIC;
ALTER TABLE visualai_learning.concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.concepts FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.concepts
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.concepts FROM PUBLIC;
ALTER TABLE visualai_learning.content_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.content_concepts FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.content_concepts
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.content_concepts FROM PUBLIC;
ALTER TABLE visualai_learning.content_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.content_units FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.content_units
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.content_units FROM PUBLIC;
CREATE TRIGGER generated_videos_set_updated_at BEFORE UPDATE ON visualai_learning.generated_videos FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.generated_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.generated_videos FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.generated_videos
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.generated_videos FROM PUBLIC;
CREATE TRIGGER learning_profiles_set_updated_at BEFORE UPDATE ON visualai_learning.learning_profiles FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.learning_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.learning_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.learning_profiles
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.learning_profiles FROM PUBLIC;
ALTER TABLE visualai_learning.learning_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.learning_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.learning_sessions
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.learning_sessions FROM PUBLIC;
ALTER TABLE visualai_learning.misconceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.misconceptions FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.misconceptions
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.misconceptions FROM PUBLIC;
CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON visualai_learning.profiles FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.profiles
    USING (id=visualai_learning_private.owner_id())
    WITH CHECK (id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.profiles FROM PUBLIC;
CREATE TRIGGER canonical_remediation_video_completion BEFORE UPDATE ON visualai_learning.remediation_jobs FOR EACH ROW EXECUTE FUNCTION visualai_learning_private.validate_remediation_video_completion();
CREATE TRIGGER remediation_jobs_set_updated_at BEFORE UPDATE ON visualai_learning.remediation_jobs FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.remediation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.remediation_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.remediation_jobs
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.remediation_jobs FROM PUBLIC;
ALTER TABLE visualai_learning.source_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.source_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.source_versions
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.source_versions FROM PUBLIC;
CREATE TRIGGER sources_set_updated_at BEFORE UPDATE ON visualai_learning.sources FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.sources FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.sources
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.sources FROM PUBLIC;
ALTER TABLE visualai_learning.subtopics ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.subtopics FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.subtopics
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.subtopics FROM PUBLIC;
ALTER TABLE visualai_learning.topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.topics FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.topics
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.topics FROM PUBLIC;
CREATE TRIGGER video_target_matrices_set_updated_at BEFORE UPDATE ON visualai_learning.video_target_matrices FOR EACH ROW EXECUTE FUNCTION visualai_learning.visualai_set_updated_at();
ALTER TABLE visualai_learning.video_target_matrices ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_learning.video_target_matrices FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_access ON visualai_learning.video_target_matrices
    USING (user_id=visualai_learning_private.owner_id())
    WITH CHECK (user_id=visualai_learning_private.owner_id());
REVOKE ALL ON visualai_learning.video_target_matrices FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA visualai_learning, visualai_learning_private FROM PUBLIC;

