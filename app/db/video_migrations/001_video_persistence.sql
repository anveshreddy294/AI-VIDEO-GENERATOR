-- Separate private local schema; existing Supabase migrations/tables are untouched.
CREATE SCHEMA IF NOT EXISTS visualai_video;
REVOKE ALL ON SCHEMA visualai_video FROM PUBLIC;

CREATE TABLE visualai_video.lessons (
    owner_id uuid NOT NULL,
    lesson_id text NOT NULL CHECK (lesson_id ~ '^[A-Za-z0-9_-]{1,128}$'),
    source_id text,
    source_version integer CHECK (source_version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    PRIMARY KEY (owner_id, lesson_id),
    CHECK ((source_id IS NULL) = (source_version IS NULL)),
    CHECK ((document->>'user_id' = owner_id::text AND document->>'lesson_id' = lesson_id) IS TRUE),
    CHECK ((document->'content'->>'user_id' = owner_id::text) IS TRUE)
);
CREATE INDEX lessons_owner_created ON visualai_video.lessons(owner_id, created_at DESC);
CREATE INDEX lessons_source ON visualai_video.lessons(owner_id, source_id, source_version);

CREATE TABLE visualai_video.generations (
    owner_id uuid NOT NULL,
    lesson_id text NOT NULL,
    job_id text NOT NULL CHECK (job_id ~ '^[A-Za-z0-9_-]{1,128}$'),
    prior_job_id text,
    history_index integer NOT NULL CHECK (history_index >= 0),
    status text NOT NULL CHECK (status IN ('QUEUED','PLANNING','RENDERING','GENERATING_AUDIO','ALIGNING','COMPOSITING','COMPLETED','FAILED')),
    stage text,
    progress integer NOT NULL CHECK (progress BETWEEN 0 AND 100),
    error_code text,
    indexing_status text NOT NULL CHECK (indexing_status IN ('NOT_REQUESTED','PENDING','INDEXED','FAILED')),
    created_at timestamptz NOT NULL,
    completed_at timestamptz,
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    PRIMARY KEY (owner_id, lesson_id, job_id),
    FOREIGN KEY (owner_id, lesson_id) REFERENCES visualai_video.lessons(owner_id, lesson_id),
    FOREIGN KEY (owner_id, lesson_id, prior_job_id) REFERENCES visualai_video.generations(owner_id, lesson_id, job_id) DEFERRABLE INITIALLY DEFERRED,
    CHECK ((document->>'job_id' = job_id AND document->>'status' = status) IS TRUE),
    CHECK ((document->'plan'->>'student_id' = owner_id::text) IS TRUE),
    CHECK (prior_job_id IS DISTINCT FROM job_id)
);
CREATE INDEX generations_owner_status ON visualai_video.generations(owner_id, status);
CREATE INDEX generations_index_retry ON visualai_video.generations(indexing_status) WHERE indexing_status = 'FAILED';

-- Verified HTTP user identity is set transaction-locally by the backend.
-- These are private backend tables, never exposed through PostgREST.
ALTER TABLE visualai_video.lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.lessons FORCE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.generations FORCE ROW LEVEL SECURITY;
CREATE POLICY lesson_owner ON visualai_video.lessons
    USING (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid);
CREATE POLICY generation_owner ON visualai_video.generations
    USING (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid);
REVOKE ALL ON ALL TABLES IN SCHEMA visualai_video FROM PUBLIC;
