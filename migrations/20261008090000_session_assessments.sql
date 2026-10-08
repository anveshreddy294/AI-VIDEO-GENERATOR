-- Phase 9: READY_TO_APPLY. Do not deploy automatically.
BEGIN;
-- Nullable links preserve historical assessments. New RPC creation requires a link.
ALTER TABLE public.learning_sessions ADD CONSTRAINT learning_sessions_assessment_scope_key
    UNIQUE (user_id, source_id, source_version, session_id);
ALTER TABLE public.assessment_sessions ADD COLUMN learning_session_id uuid,
    ADD COLUMN request_hash text,
    ADD CONSTRAINT assessment_learning_session_scope_fk FOREIGN KEY
        (user_id,source_id,source_version,learning_session_id)
        REFERENCES public.learning_sessions(user_id,source_id,source_version,session_id),
    ADD CONSTRAINT assessment_request_hash_check CHECK
        (learning_session_id IS NULL OR (request_hash IS NOT NULL AND request_hash ~ '^[0-9a-f]{64}$'));
ALTER TABLE public.assessment_questions ADD COLUMN evidence_ids text[] NOT NULL DEFAULT '{}';
CREATE INDEX assessment_learning_session_lookup ON public.assessment_sessions(user_id,learning_session_id);
-- No learner grants on answer-key tables. Only the verified backend may call these RPCs.
CREATE FUNCTION visualai_internal.assessment_transaction(
    p_action text,p_user_id uuid,p_assessment_id text,p_payload jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    assessment public.assessment_sessions;
    learning public.learning_sessions;
    q jsonb;
    stored public.assessment_questions;
    count_questions integer;
    selected integer;
    question_results jsonb := '[]'::jsonb;
    concept_results jsonb;
    performance jsonb;
BEGIN
    IF p_user_id IS NULL OR p_assessment_id IS NULL OR length(p_assessment_id)>128
       OR p_action NOT IN ('load','create','submit') OR p_action IS NULL THEN
        RAISE EXCEPTION 'Invalid assessment operation' USING ERRCODE='22023';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_assessment_id,0));
    SELECT * INTO assessment FROM public.assessment_sessions
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
            SELECT * INTO learning FROM public.learning_sessions
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
            INSERT INTO public.assessment_sessions(session_id,user_id,source_id,source_version,
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
                INSERT INTO public.assessment_questions(question_id,user_id,source_id,source_version,session_id,
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
            SELECT * INTO assessment FROM public.assessment_sessions WHERE session_id=p_assessment_id;
        END IF;
    ELSIF p_action='submit' THEN
        IF assessment.session_id IS NULL THEN RETURN NULL; END IF;
        SELECT * INTO learning FROM public.learning_sessions
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
            SELECT count(*) INTO count_questions FROM public.assessment_questions
                WHERE session_id=p_assessment_id AND user_id=p_user_id;
            IF assessment.status<>'READY' OR count_questions=0
               OR jsonb_typeof(p_payload->'answers') IS DISTINCT FROM 'object'
               OR (SELECT count(*) FROM jsonb_object_keys(p_payload->'answers'))<>count_questions
               OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_payload->'answers') a(id)
                   WHERE NOT EXISTS(SELECT 1 FROM public.assessment_questions q2
                       WHERE q2.session_id=p_assessment_id AND q2.user_id=p_user_id AND q2.question_id=a.id)) THEN
                RAISE EXCEPTION 'Invalid assessment answers' USING ERRCODE='22023';
            END IF;
            FOR stored IN SELECT * FROM public.assessment_questions
                WHERE session_id=p_assessment_id AND user_id=p_user_id ORDER BY question_id LOOP
                IF jsonb_typeof(p_payload->'answers'->stored.question_id) IS DISTINCT FROM 'number'
                   OR (p_payload->'answers'->>stored.question_id) !~ '^[0-3]$' THEN
                    RAISE EXCEPTION 'Invalid assessment answers' USING ERRCODE='22023';
                END IF;
                selected := (p_payload->'answers'->>stored.question_id)::integer;
                INSERT INTO public.assessment_attempts(attempt_id,user_id,source_id,source_version,session_id,
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
                FROM public.assessment_attempts WHERE session_id=p_assessment_id AND user_id=p_user_id GROUP BY concept_id
            ) t;
            performance := jsonb_build_object('session_id',p_assessment_id,'learning_session_id',assessment.learning_session_id,
                'source_id',assessment.source_id,'source_version',assessment.source_version,
                'question_results',question_results,'concept_results',concept_results,'overall_score',
                (SELECT 100.0*count(*) FILTER(WHERE is_correct)/count(*) FROM public.assessment_attempts
                    WHERE session_id=p_assessment_id AND user_id=p_user_id));
            UPDATE public.assessment_sessions SET status='SUBMITTED',submitted_answers=p_payload->'answers',
                submission_response=performance,submitted_at=clock_timestamp()
                WHERE session_id=p_assessment_id AND user_id=p_user_id;
            SELECT * INTO assessment FROM public.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id;
        END IF;
    END IF;
    IF assessment.session_id IS NULL THEN RETURN NULL; END IF;
    RETURN to_jsonb(assessment) || jsonb_build_object('student_id',p_user_id::text,'questions',
        (SELECT coalesce(jsonb_agg(to_jsonb(q3) ORDER BY question_id),'[]'::jsonb)
         FROM public.assessment_questions q3 WHERE session_id=p_assessment_id AND user_id=p_user_id));
END $$;
CREATE FUNCTION public.visualai_assessment_transaction(p_action text,p_user_id uuid,p_assessment_id text,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
    SELECT visualai_internal.assessment_transaction(p_action,p_user_id,p_assessment_id,p_payload)
$$;
REVOKE ALL ON FUNCTION visualai_internal.assessment_transaction(text,uuid,text,jsonb),
    public.visualai_assessment_transaction(text,uuid,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT USAGE ON SCHEMA visualai_internal TO service_role;
GRANT EXECUTE ON FUNCTION visualai_internal.assessment_transaction(text,uuid,text,jsonb),
    public.visualai_assessment_transaction(text,uuid,text,jsonb) TO service_role;
COMMIT;
