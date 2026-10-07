-- Additive Phase 6A.2. Apply only this file after the three deployed migrations.
-- Never replay 001. No change to Phase 5B ingestion, Auth, or existing RLS/grants.
BEGIN;

CREATE TABLE public.topics (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    topic_id text NOT NULL CHECK (topic_id <> ''),
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text,
    sequence integer NOT NULL CHECK (sequence >= 0),
    provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object'),
    PRIMARY KEY (user_id, source_id, source_version, topic_id),
    UNIQUE (user_id, source_id, source_version, sequence),
    FOREIGN KEY (user_id, source_id, source_version)
        REFERENCES public.source_versions(user_id, source_id, version) ON DELETE CASCADE
);

CREATE TABLE public.subtopics (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    subtopic_id text NOT NULL CHECK (subtopic_id <> ''),
    topic_id text NOT NULL,
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text,
    sequence integer NOT NULL CHECK (sequence >= 0),
    provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object'),
    PRIMARY KEY (user_id, source_id, source_version, subtopic_id),
    UNIQUE (user_id, source_id, source_version, topic_id, sequence),
    FOREIGN KEY (user_id, source_id, source_version, topic_id)
        REFERENCES public.topics(user_id, source_id, source_version, topic_id) ON DELETE CASCADE
);

ALTER TABLE public.concepts
    ADD COLUMN subtopic_id text,
    ADD COLUMN sequence integer CHECK (sequence >= 0),
    ADD COLUMN provenance jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(provenance) = 'object'),
    ADD CONSTRAINT concepts_subtopic_scope_fk
        FOREIGN KEY (user_id, source_id, source_version, subtopic_id)
        REFERENCES public.subtopics(user_id, source_id, source_version, subtopic_id)
            ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT concepts_membership_pair_check
        CHECK ((subtopic_id IS NULL) = (sequence IS NULL));
CREATE UNIQUE INDEX concepts_subtopic_sequence_idx
    ON public.concepts(user_id, source_id, source_version, subtopic_id, sequence)
    WHERE subtopic_id IS NOT NULL;

CREATE TABLE public.content_concepts (
    user_id uuid NOT NULL,
    source_id text NOT NULL,
    source_version integer NOT NULL,
    content_id text NOT NULL,
    concept_id text NOT NULL,
    support_kind text NOT NULL CHECK (support_kind IN
        ('definition', 'explanation', 'example', 'prerequisite_evidence')),
    char_start integer,
    char_end integer,
    extraction_confidence numeric CHECK (extraction_confidence BETWEEN 0 AND 1),
    provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object'),
    PRIMARY KEY (user_id, source_id, source_version, content_id, concept_id, support_kind),
    FOREIGN KEY (user_id, source_id, source_version, content_id)
        REFERENCES public.content_units(user_id, source_id, source_version, content_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, source_id, source_version, concept_id)
        REFERENCES public.concepts(user_id, source_id, source_version, concept_id) ON DELETE CASCADE,
    CHECK ((char_start IS NULL AND char_end IS NULL)
        OR (char_start IS NOT NULL AND char_end IS NOT NULL
            AND char_start >= 0 AND char_end > char_start))
);
CREATE INDEX content_concepts_concept_idx
    ON public.content_concepts(user_id, source_id, source_version, concept_id, content_id);

ALTER TABLE public.concept_relationships
    ADD COLUMN provenance jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(provenance) = 'object'),
    ADD COLUMN evidence_content_ids text[] NOT NULL DEFAULT '{}'::text[];

ALTER TABLE public.source_versions
    ADD COLUMN knowledge_state text NOT NULL DEFAULT 'LEGACY_UNMAPPED'
        CHECK (knowledge_state IN ('PENDING', 'READY', 'FAILED', 'LEGACY_UNMAPPED')),
    ADD COLUMN knowledge_schema_version integer,
    ADD COLUMN knowledge_operation_id uuid,
    ADD COLUMN knowledge_payload_hash text,
    ADD COLUMN knowledge_committed_at timestamptz,
    ADD COLUMN knowledge_diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(knowledge_diagnostics) = 'object'),
    ADD CONSTRAINT knowledge_commit_metadata_check CHECK (
        (knowledge_state = 'READY' AND knowledge_schema_version = 1
            AND knowledge_schema_version IS NOT NULL
            AND knowledge_operation_id IS NOT NULL
            AND knowledge_payload_hash IS NOT NULL
            AND knowledge_payload_hash ~ '^[0-9a-f]{64}$'
            AND knowledge_committed_at IS NOT NULL)
        OR (knowledge_state <> 'READY' AND knowledge_schema_version IS NULL
            AND knowledge_operation_id IS NULL AND knowledge_payload_hash IS NULL
            AND knowledge_committed_at IS NULL));
CREATE UNIQUE INDEX source_versions_knowledge_operation_idx
    ON public.source_versions(user_id, knowledge_operation_id)
    WHERE knowledge_operation_id IS NOT NULL;

ALTER TABLE public.topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subtopics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_concepts ENABLE ROW LEVEL SECURITY;
CREATE POLICY topics_owner_select ON public.topics FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = user_id);
CREATE POLICY subtopics_owner_select ON public.subtopics FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = user_id);
CREATE POLICY content_concepts_owner_select ON public.content_concepts FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = user_id);
REVOKE ALL ON public.topics, public.subtopics, public.content_concepts
    FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.topics, public.subtopics, public.content_concepts TO authenticated;

-- Private helpers are not callable by application roles. No dynamic SQL.
CREATE FUNCTION visualai_internal.knowledge_object(
    p_value jsonb, p_required text[], p_types jsonb)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $function$
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

-- JSON object order, whitespace and numeric scale do not change the hash.
-- Array order is part of the snapshot contract. Bound arbitrary provenance depth.
CREATE FUNCTION visualai_internal.knowledge_canonical_json(p_value jsonb, p_depth integer DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path = '' AS $function$
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
            visualai_internal.knowledge_canonical_json(e.value, p_depth + 1) ORDER BY e.ordinality), '[]'::jsonb)
            INTO result FROM pg_catalog.jsonb_array_elements(p_value) WITH ORDINALITY e;
    WHEN 'object' THEN
        SELECT COALESCE(pg_catalog.jsonb_object_agg(e.key,
            visualai_internal.knowledge_canonical_json(e.value, p_depth + 1)), '{}'::jsonb)
            INTO result FROM pg_catalog.jsonb_each(p_value) e;
    ELSE RETURN p_value;
    END CASE;
    RETURN result;
END;
$function$;

CREATE FUNCTION visualai_internal.commit_knowledge_snapshot(
    p_source_id text, p_source_version integer, p_operation_id uuid, p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = '' SET lock_timeout = '5s' AS $function$
DECLARE
    caller uuid := auth.uid();
    snapshot public.source_versions;
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
    PERFORM visualai_internal.knowledge_object(p_payload,
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
        PERFORM visualai_internal.knowledge_object(item,
            ARRAY['topic_id','title','sequence','provenance'],
            '{"topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'subtopics') LOOP
        PERFORM visualai_internal.knowledge_object(item,
            ARRAY['subtopic_id','topic_id','title','sequence','provenance'],
            '{"subtopic_id":"string","topic_id":"string","title":"string","description":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') LOOP
        PERFORM visualai_internal.knowledge_object(item,
            ARRAY['concept_id','subtopic_id','name','sequence','provenance'],
            '{"concept_id":"string","subtopic_id":"string","name":"string","definition":"string","sequence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'content_concepts') LOOP
        PERFORM visualai_internal.knowledge_object(item,
            ARRAY['content_id','concept_id','support_kind','provenance'],
            '{"content_id":"string","concept_id":"string","support_kind":"string","char_start":"number","char_end":"number","extraction_confidence":"number","provenance":"object"}');
    END LOOP;
    FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_payload->'relationships') LOOP
        PERFORM visualai_internal.knowledge_object(item,
            ARRAY['concept_id','related_concept_id','relationship_type','evidence_content_ids','provenance'],
            '{"concept_id":"string","related_concept_id":"string","relationship_type":"string","evidence_content_ids":"array","provenance":"object"}');
        IF pg_catalog.jsonb_array_length(item->'evidence_content_ids') NOT BETWEEN 1 AND 64
            OR EXISTS (SELECT 1 FROM pg_catalog.jsonb_array_elements(item->'evidence_content_ids') e
                WHERE pg_catalog.jsonb_typeof(e.value) <> 'string') THEN
            RAISE EXCEPTION 'KNOWLEDGE_INVALID_EDGE_EVIDENCE' USING ERRCODE = '22023';
        END IF;
    END LOOP;

    payload_hash := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        visualai_internal.knowledge_canonical_json(p_payload)::text, 'UTF8')), 'hex');
    SELECT * INTO snapshot FROM public.source_versions
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
                LEFT JOIN public.content_units u ON u.user_id = caller AND u.source_id = p_source_id
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
        IF EXISTS (SELECT 1 FROM public.concepts c WHERE c.user_id = caller AND c.source_id = p_source_id
                AND c.source_version = p_source_version AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_payload->'concepts') n
                    WHERE n->>'concept_id' = c.concept_id))
            OR EXISTS (SELECT 1 FROM public.concept_relationships r WHERE r.user_id = caller
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

        INSERT INTO public.topics(user_id, source_id, source_version, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'topics')
                x(topic_id text, title text, description text, sequence integer, provenance jsonb);
        INSERT INTO public.subtopics(user_id, source_id, source_version, subtopic_id, topic_id, title, description, sequence, provenance)
            SELECT caller, p_source_id, p_source_version, x.subtopic_id, x.topic_id, x.title, x.description, x.sequence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'subtopics')
                x(subtopic_id text, topic_id text, title text, description text, sequence integer, provenance jsonb);
        INSERT INTO public.concepts(user_id, source_id, source_version, concept_id, name, definition,
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
        INSERT INTO public.content_concepts(user_id, source_id, source_version, content_id, concept_id,
            support_kind, char_start, char_end, extraction_confidence, provenance)
            SELECT caller, p_source_id, p_source_version, x.content_id, x.concept_id, x.support_kind,
                x.char_start, x.char_end, x.extraction_confidence, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'content_concepts')
                x(content_id text, concept_id text, support_kind text, char_start integer, char_end integer,
                    extraction_confidence numeric, provenance jsonb);
        INSERT INTO public.concept_relationships(user_id, source_id, source_version, concept_id,
            related_concept_id, relationship_type, evidence_content_ids, provenance)
            SELECT caller, p_source_id, p_source_version, x.concept_id, x.related_concept_id,
                x.relationship_type, x.evidence_content_ids, x.provenance
            FROM pg_catalog.jsonb_to_recordset(p_payload->'relationships')
                x(concept_id text, related_concept_id text, relationship_type text,
                    evidence_content_ids text[], provenance jsonb)
            ON CONFLICT (source_id, source_version, concept_id, related_concept_id, relationship_type)
                DO UPDATE SET evidence_content_ids = EXCLUDED.evidence_content_ids, provenance = EXCLUDED.provenance;
        UPDATE public.source_versions SET knowledge_state = 'READY', knowledge_schema_version = 1,
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

CREATE FUNCTION public.visualai_commit_knowledge_snapshot(
    p_source_id text, p_source_version integer, p_operation_id uuid, p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path = '' AS $function$
    SELECT visualai_internal.commit_knowledge_snapshot(p_source_id, p_source_version, p_operation_id, p_payload);
$function$;
REVOKE ALL ON FUNCTION visualai_internal.knowledge_object(jsonb, text[], jsonb),
    visualai_internal.knowledge_canonical_json(jsonb, integer) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION visualai_internal.commit_knowledge_snapshot(text, integer, uuid, jsonb),
    public.visualai_commit_knowledge_snapshot(text, integer, uuid, jsonb) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION visualai_internal.commit_knowledge_snapshot(text, integer, uuid, jsonb),
    public.visualai_commit_knowledge_snapshot(text, integer, uuid, jsonb) TO authenticated;
COMMIT;
