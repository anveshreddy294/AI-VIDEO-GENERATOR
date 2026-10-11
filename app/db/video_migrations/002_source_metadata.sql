-- Metadata copies only. Supabase remains the canonical ingestion/knowledge store.
CREATE TABLE visualai_video.sources (
    owner_id uuid NOT NULL,
    source_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    copied_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, source_id),
    CHECK ((document->>'user_id' = owner_id::text AND document->>'source_id' = source_id
        AND (document->>'version')::integer = version) IS TRUE)
);
CREATE TABLE visualai_video.source_versions (
    owner_id uuid NOT NULL,
    source_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    copied_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, source_id, version),
    FOREIGN KEY (owner_id, source_id) REFERENCES visualai_video.sources(owner_id, source_id),
    CHECK ((document->>'user_id' = owner_id::text AND document->>'source_id' = source_id
        AND (document->>'version')::integer = version) IS TRUE),
    CHECK (NOT document ?| ARRAY['normalized_content','sanitized_content','quarantined_content',
        'rich_chunks','topic_blueprint','knowledge_diagnostics'])
);
ALTER TABLE visualai_video.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.sources FORCE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.source_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visualai_video.source_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY source_metadata_owner ON visualai_video.sources
    USING (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid);
CREATE POLICY source_version_metadata_owner ON visualai_video.source_versions
    USING (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = nullif(current_setting('visualai.owner_id', true), '')::uuid);
REVOKE ALL ON visualai_video.sources, visualai_video.source_versions FROM PUBLIC;
