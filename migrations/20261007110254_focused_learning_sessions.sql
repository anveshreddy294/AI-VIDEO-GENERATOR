-- Phase 6D. Pending explicit remote deployment approval; never bulk-push history.
BEGIN;
CREATE TABLE public.learning_sessions (
    session_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id),
    source_id text NOT NULL,
    source_version integer NOT NULL CHECK (source_version > 0),
    topic_id text NOT NULL,
    subtopic_id text,
    selected_concept_ids text[] NOT NULL CHECK (
        cardinality(selected_concept_ids) BETWEEN 1 AND 64
        AND array_position(selected_concept_ids, NULL) IS NULL),
    state text NOT NULL DEFAULT 'ACTIVE' CHECK (state IN ('ACTIVE','COMPLETED','ABANDONED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_active_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (user_id,source_id,source_version,topic_id)
        REFERENCES public.topics(user_id,source_id,source_version,topic_id),
    FOREIGN KEY (user_id,source_id,source_version,subtopic_id)
        REFERENCES public.subtopics(user_id,source_id,source_version,subtopic_id)
);
CREATE INDEX learning_sessions_owner_active_idx ON public.learning_sessions(user_id,last_active_at DESC);
ALTER TABLE public.learning_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.learning_sessions FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.learning_sessions TO authenticated;
CREATE POLICY learning_session_owner_read ON public.learning_sessions
    FOR SELECT TO authenticated USING ((select auth.uid()) = user_id);

CREATE FUNCTION visualai_internal.mutate_learning_session(
    p_action text, p_session_id uuid, p_source_id text DEFAULT NULL,
    p_source_version integer DEFAULT NULL, p_topic_id text DEFAULT NULL,
    p_subtopic_id text DEFAULT NULL, p_concept_ids text[] DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    owner_id uuid := auth.uid();
    existing public.learning_sessions;
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
    SELECT * INTO existing FROM public.learning_sessions
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
        IF NOT EXISTS (SELECT 1 FROM public.source_versions
            WHERE user_id=owner_id AND source_id=p_source_id AND version=p_source_version
                AND knowledge_state='READY') OR NOT EXISTS (SELECT 1 FROM public.topics
            WHERE user_id=owner_id AND source_id=p_source_id AND source_version=p_source_version
                AND topic_id=p_topic_id) OR (p_subtopic_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.subtopics WHERE user_id=owner_id AND source_id=p_source_id
                AND source_version=p_source_version AND topic_id=p_topic_id AND subtopic_id=p_subtopic_id)) THEN
            RAISE EXCEPTION 'Selection unavailable' USING ERRCODE='42501';
        END IF;
        SELECT array_agg(c.concept_id ORDER BY c.concept_id) INTO resolved
            FROM public.concepts c JOIN public.subtopics s
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
            IF EXISTS (SELECT 1 FROM public.learning_sessions WHERE session_id=p_session_id) THEN
                RAISE EXCEPTION 'Session unavailable' USING ERRCODE='42501';
            END IF;
            INSERT INTO public.learning_sessions(session_id,user_id,source_id,source_version,topic_id,subtopic_id,selected_concept_ids)
                VALUES(p_session_id,owner_id,p_source_id,p_source_version,p_topic_id,p_subtopic_id,resolved)
                RETURNING * INTO existing;
        ELSE
            UPDATE public.learning_sessions SET topic_id=p_topic_id,subtopic_id=p_subtopic_id,
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
        UPDATE public.learning_sessions SET
            state=CASE p_action WHEN 'complete' THEN 'COMPLETED' WHEN 'abandon' THEN 'ABANDONED' ELSE 'ACTIVE' END,
            updated_at=instant,last_active_at=instant
            WHERE session_id=p_session_id AND user_id=owner_id RETURNING * INTO existing;
    END IF;
    RETURN to_jsonb(existing);
END $$;
REVOKE ALL ON FUNCTION visualai_internal.mutate_learning_session(text,uuid,text,integer,text,text,text[])
    FROM PUBLIC,anon,authenticated,service_role;
GRANT USAGE ON SCHEMA visualai_internal TO authenticated;
GRANT EXECUTE ON FUNCTION visualai_internal.mutate_learning_session(text,uuid,text,integer,text,text,text[])
    TO authenticated;
CREATE FUNCTION public.visualai_mutate_learning_session(
    p_action text,p_session_id uuid,p_source_id text DEFAULT NULL,p_source_version integer DEFAULT NULL,
    p_topic_id text DEFAULT NULL,p_subtopic_id text DEFAULT NULL,p_concept_ids text[] DEFAULT NULL
) RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
    SELECT visualai_internal.mutate_learning_session(p_action,p_session_id,p_source_id,p_source_version,p_topic_id,p_subtopic_id,p_concept_ids)
$$;
REVOKE ALL ON FUNCTION public.visualai_mutate_learning_session(text,uuid,text,integer,text,text,text[])
    FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.visualai_mutate_learning_session(text,uuid,text,integer,text,text,text[]) TO authenticated;
COMMIT;
