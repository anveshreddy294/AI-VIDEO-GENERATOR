-- Phase 10: READY_TO_APPLY, after 20261008090000_session_assessments.sql.
-- Historical rows stay separate; no remote deployment is authorized.
BEGIN;
ALTER TABLE public.learning_sessions ADD COLUMN mastery_revision integer NOT NULL DEFAULT 0 CHECK(mastery_revision>=0);
ALTER TABLE public.assessment_sessions ADD COLUMN mastery_applied_at timestamptz,
    ADD COLUMN assessment_type text NOT NULL DEFAULT 'DIAGNOSTIC' CHECK(assessment_type IN ('DIAGNOSTIC','REASSESSMENT')),
    ADD COLUMN reassessment_job_id text;
ALTER TABLE public.concept_mastery DROP CONSTRAINT concept_mastery_pkey,
    ADD COLUMN mastery_id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    ADD COLUMN consecutive_correct integer NOT NULL DEFAULT 0 CHECK(consecutive_correct>=0);
ALTER TABLE public.concept_mastery ADD COLUMN learning_session_id uuid,
    ADD CONSTRAINT concept_mastery_learning_scope_fk FOREIGN KEY(user_id,source_id,source_version,learning_session_id)
    REFERENCES public.learning_sessions(user_id,source_id,source_version,session_id);
CREATE INDEX concept_mastery_learning_lookup ON public.concept_mastery(user_id,learning_session_id);
ALTER TABLE public.misconceptions ADD COLUMN learning_session_id uuid,
    ADD CONSTRAINT misconceptions_learning_scope_fk FOREIGN KEY(user_id,source_id,source_version,learning_session_id)
    REFERENCES public.learning_sessions(user_id,source_id,source_version,session_id);
CREATE INDEX misconceptions_learning_lookup ON public.misconceptions(user_id,learning_session_id);
ALTER TABLE public.remediation_jobs ADD COLUMN learning_session_id uuid,
    ADD CONSTRAINT remediation_jobs_learning_scope_fk FOREIGN KEY(user_id,source_id,source_version,learning_session_id)
    REFERENCES public.learning_sessions(user_id,source_id,source_version,session_id);
CREATE INDEX remediation_jobs_learning_lookup ON public.remediation_jobs(user_id,learning_session_id);
CREATE UNIQUE INDEX concept_mastery_legacy_scope ON public.concept_mastery(user_id,source_id,source_version,concept_id) WHERE learning_session_id IS NULL;
CREATE UNIQUE INDEX concept_mastery_learning_scope ON public.concept_mastery(user_id,source_id,source_version,learning_session_id,concept_id) WHERE learning_session_id IS NOT NULL;
CREATE UNIQUE INDEX misconceptions_learning_scope ON public.misconceptions(user_id,learning_session_id,concept_id) WHERE learning_session_id IS NOT NULL;
ALTER TABLE public.assessment_sessions ADD CONSTRAINT assessment_remediation_fk FOREIGN KEY(reassessment_job_id) REFERENCES public.remediation_jobs(remediation_job_id);
CREATE FUNCTION visualai_internal.learning_transaction(p_action text,p_user_id uuid,p_learning_session_id uuid,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    learning public.learning_sessions;
    assessment public.assessment_sessions;
    job public.remediation_jobs;
    item jsonb;
    target_table text;
    evidence_id text;
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('load','finalize','complete') OR p_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid learning operation' USING ERRCODE='22023';
    END IF;
    SELECT * INTO learning FROM public.learning_sessions WHERE session_id=p_learning_session_id AND user_id=p_user_id FOR UPDATE;
    IF learning.session_id IS NULL THEN RETURN NULL; END IF;
    IF p_action<>'load' THEN
        IF learning.state<>'ACTIVE' OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023';
        END IF;
        IF p_action='finalize' THEN
            SELECT * INTO assessment FROM public.assessment_sessions WHERE session_id=p_payload->>'assessment_id'
                AND user_id=p_user_id AND learning_session_id=p_learning_session_id
                AND source_id=learning.source_id AND source_version=learning.source_version FOR UPDATE;
            IF assessment.session_id IS NULL OR assessment.status<>'SUBMITTED' THEN RETURN NULL; END IF;
            IF assessment.mastery_applied_at IS NOT NULL THEN
                RETURN visualai_internal.learning_transaction('load',p_user_id,p_learning_session_id,'{}');
            END IF;
            IF EXISTS(SELECT 1 FROM public.assessment_sessions a WHERE a.user_id=p_user_id
                AND a.learning_session_id=p_learning_session_id AND a.status='SUBMITTED' AND a.mastery_applied_at IS NULL
                AND (a.submitted_at,a.session_id)<(assessment.submitted_at,assessment.session_id)) THEN
                RAISE EXCEPTION 'Earlier assessment pending' USING ERRCODE='23505';
            END IF;
        ELSE
            SELECT * INTO job FROM public.remediation_jobs WHERE remediation_job_id=p_payload->>'job_id'
                AND user_id=p_user_id AND learning_session_id=p_learning_session_id FOR UPDATE;
            IF job.remediation_job_id IS NULL THEN RETURN NULL; END IF;
            IF job.metadata->>'completed'='true' THEN
                RETURN visualai_internal.learning_transaction('load',p_user_id,p_learning_session_id,'{}');
            END IF;
            IF job.status<>'READY' OR NOT EXISTS(SELECT 1 FROM public.concept_mastery m
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
                   OR NOT EXISTS(SELECT 1 FROM public.concepts c WHERE c.user_id=p_user_id AND c.source_id=learning.source_id
                        AND c.source_version=learning.source_version AND c.concept_id=item->>'concept_id') THEN
                    RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023';
                END IF;
                FOR evidence_id IN SELECT jsonb_array_elements_text(coalesce(item->'evidence_attempt_ids',item->'processed_attempt_ids','[]')) LOOP
                    IF NOT EXISTS(SELECT 1 FROM public.assessment_attempts a JOIN public.assessment_sessions s
                        ON s.session_id=a.session_id AND s.user_id=a.user_id WHERE a.attempt_id=evidence_id
                        AND a.user_id=p_user_id AND s.learning_session_id=p_learning_session_id AND a.concept_id=item->>'concept_id') THEN
                        RAISE EXCEPTION 'Learning evidence unavailable' USING ERRCODE='22023';
                    END IF;
                END LOOP;
            END LOOP;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'mastery') LOOP
            INSERT INTO public.concept_mastery(user_id,source_id,source_version,concept_id,session_id,attempt_count,correct_count,incorrect_count,reassessment_attempt_count,reassessment_correct_count,lifetime_accuracy,mastery_score,mastery_state,remediation_attempt_count,processed_attempt_ids,last_assessed_at,last_remediation_at,created_at,updated_at,learning_session_id,consecutive_correct)
            SELECT user_id,source_id,source_version,concept_id,session_id,attempt_count,correct_count,incorrect_count,reassessment_attempt_count,reassessment_correct_count,lifetime_accuracy,mastery_score,mastery_state,remediation_attempt_count,processed_attempt_ids,last_assessed_at,last_remediation_at,created_at,updated_at,learning_session_id,consecutive_correct FROM jsonb_populate_record(NULL::public.concept_mastery,item)
            ON CONFLICT (user_id,source_id,source_version,learning_session_id,concept_id) WHERE learning_session_id IS NOT NULL DO UPDATE SET session_id=EXCLUDED.session_id,attempt_count=EXCLUDED.attempt_count,correct_count=EXCLUDED.correct_count,incorrect_count=EXCLUDED.incorrect_count,reassessment_attempt_count=EXCLUDED.reassessment_attempt_count,reassessment_correct_count=EXCLUDED.reassessment_correct_count,lifetime_accuracy=EXCLUDED.lifetime_accuracy,mastery_score=EXCLUDED.mastery_score,mastery_state=EXCLUDED.mastery_state,remediation_attempt_count=EXCLUDED.remediation_attempt_count,processed_attempt_ids=EXCLUDED.processed_attempt_ids,last_assessed_at=EXCLUDED.last_assessed_at,last_remediation_at=EXCLUDED.last_remediation_at,updated_at=EXCLUDED.updated_at,consecutive_correct=EXCLUDED.consecutive_correct;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'gaps') LOOP
            INSERT INTO public.misconceptions(misconception_id,user_id,source_id,source_version,session_id,concept_id,misconception_code,misconception_label,misconception_description,misconception_type,evidence_question_ids,evidence_attempt_ids,occurrence_count,confidence_state,status,first_detected_at,last_detected_at,corrected_at,source_chunk_ids,supporting_evidence_summary,learning_session_id)
            SELECT misconception_id,user_id,source_id,source_version,session_id,concept_id,misconception_code,misconception_label,misconception_description,misconception_type,evidence_question_ids,evidence_attempt_ids,occurrence_count,confidence_state,status,first_detected_at,last_detected_at,corrected_at,source_chunk_ids,supporting_evidence_summary,learning_session_id FROM jsonb_populate_record(NULL::public.misconceptions,item)
            ON CONFLICT (misconception_id) DO UPDATE SET session_id=EXCLUDED.session_id,concept_id=EXCLUDED.concept_id,misconception_code=EXCLUDED.misconception_code,misconception_label=EXCLUDED.misconception_label,misconception_description=EXCLUDED.misconception_description,misconception_type=EXCLUDED.misconception_type,evidence_question_ids=EXCLUDED.evidence_question_ids,evidence_attempt_ids=EXCLUDED.evidence_attempt_ids,occurrence_count=EXCLUDED.occurrence_count,confidence_state=EXCLUDED.confidence_state,status=EXCLUDED.status,first_detected_at=EXCLUDED.first_detected_at,last_detected_at=EXCLUDED.last_detected_at,corrected_at=EXCLUDED.corrected_at,source_chunk_ids=EXCLUDED.source_chunk_ids,supporting_evidence_summary=EXCLUDED.supporting_evidence_summary WHERE misconceptions.user_id=p_user_id AND misconceptions.learning_session_id=p_learning_session_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'remediation') LOOP
            INSERT INTO public.remediation_jobs(remediation_job_id,user_id,source_id,source_version,session_id,concept_id,status,video_job_id,video_path,duration_seconds,attempt_number,idempotency_key,strategy_used,misconception_code,evidence_attempt_ids,started_at,completed_at,failed_at,failure_code,failure_message,is_infrastructure_failure,metadata,created_at,updated_at,learning_session_id)
            SELECT remediation_job_id,user_id,source_id,source_version,session_id,concept_id,status,video_job_id,video_path,duration_seconds,attempt_number,idempotency_key,strategy_used,misconception_code,evidence_attempt_ids,started_at,completed_at,failed_at,failure_code,failure_message,is_infrastructure_failure,metadata,created_at,updated_at,learning_session_id FROM jsonb_populate_record(NULL::public.remediation_jobs,item||jsonb_build_object('updated_at',clock_timestamp()))
            ON CONFLICT (remediation_job_id) DO UPDATE SET session_id=EXCLUDED.session_id,concept_id=EXCLUDED.concept_id,status=EXCLUDED.status,video_job_id=EXCLUDED.video_job_id,video_path=EXCLUDED.video_path,duration_seconds=EXCLUDED.duration_seconds,attempt_number=EXCLUDED.attempt_number,idempotency_key=EXCLUDED.idempotency_key,strategy_used=EXCLUDED.strategy_used,misconception_code=EXCLUDED.misconception_code,evidence_attempt_ids=EXCLUDED.evidence_attempt_ids,started_at=EXCLUDED.started_at,completed_at=EXCLUDED.completed_at,failed_at=EXCLUDED.failed_at,failure_code=EXCLUDED.failure_code,failure_message=EXCLUDED.failure_message,is_infrastructure_failure=EXCLUDED.is_infrastructure_failure,metadata=EXCLUDED.metadata,updated_at=EXCLUDED.updated_at WHERE remediation_jobs.user_id=p_user_id AND remediation_jobs.learning_session_id=p_learning_session_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Learning scope unavailable' USING ERRCODE='22023'; END IF;
        END LOOP;
        IF p_action='finalize' THEN
            UPDATE public.assessment_sessions SET mastery_applied_at=clock_timestamp()
                WHERE session_id=assessment.session_id AND user_id=p_user_id;
        END IF;
        UPDATE public.learning_sessions SET mastery_revision=mastery_revision+1 WHERE session_id=p_learning_session_id AND user_id=p_user_id;
    END IF;
    RETURN jsonb_build_object('revision',(SELECT mastery_revision FROM public.learning_sessions WHERE session_id=p_learning_session_id AND user_id=p_user_id),
        'mastery',(SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY concept_id),'[]') FROM public.concept_mastery m WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'gaps',(SELECT coalesce(jsonb_agg(to_jsonb(g) ORDER BY concept_id),'[]') FROM public.misconceptions g WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'remediation',(SELECT coalesce(jsonb_agg(to_jsonb(j) ORDER BY created_at,remediation_job_id),'[]') FROM public.remediation_jobs j WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id),
        'attempts',(SELECT coalesce(jsonb_agg(to_jsonb(a)||jsonb_build_object('learning_session_id',s.learning_session_id) ORDER BY a.submitted_at,a.attempt_id),'[]')
            FROM public.assessment_attempts a JOIN public.assessment_sessions s ON s.session_id=a.session_id AND s.user_id=a.user_id
            WHERE a.user_id=p_user_id AND s.learning_session_id=p_learning_session_id AND a.source_id=learning.source_id AND a.source_version=learning.source_version),
        'applied_assessments',(SELECT coalesce(jsonb_agg(session_id ORDER BY submitted_at,session_id),'[]') FROM public.assessment_sessions
            WHERE user_id=p_user_id AND learning_session_id=p_learning_session_id AND mastery_applied_at IS NOT NULL));
END $$;
CREATE FUNCTION public.visualai_learning_transaction(p_action text,p_user_id uuid,p_learning_session_id uuid,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
    SELECT visualai_internal.learning_transaction(p_action,p_user_id,p_learning_session_id,p_payload)
$$;
REVOKE ALL ON FUNCTION visualai_internal.learning_transaction(text,uuid,uuid,jsonb),public.visualai_learning_transaction(text,uuid,uuid,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION visualai_internal.learning_transaction(text,uuid,uuid,jsonb),public.visualai_learning_transaction(text,uuid,uuid,jsonb) TO service_role;
-- Preserve Phase 9 generation/grading transactions; add atomic reassessment authorization.
ALTER FUNCTION visualai_internal.assessment_transaction(text,uuid,text,jsonb) RENAME TO assessment_transaction_phase9;
CREATE FUNCTION visualai_internal.assessment_transaction(p_action text,p_user_id uuid,p_assessment_id text,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    job public.remediation_jobs;
    learning public.learning_sessions;
    assessment public.assessment_sessions;
    result jsonb;
BEGIN
    -- Lock learning before assessment, matching mastery finalization lock order.
    IF p_action='create' THEN
        SELECT * INTO learning FROM public.learning_sessions WHERE session_id=(p_payload->>'learning_session_id')::uuid AND user_id=p_user_id FOR UPDATE;
    ELSE
        SELECT * INTO assessment FROM public.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id;
        IF assessment.learning_session_id IS NOT NULL THEN
            SELECT * INTO learning FROM public.learning_sessions WHERE session_id=assessment.learning_session_id AND user_id=p_user_id FOR UPDATE;
        END IF;
    END IF;
    IF p_action='create' AND NOT EXISTS(SELECT 1 FROM public.assessment_sessions WHERE session_id=p_assessment_id AND user_id=p_user_id) THEN
        -- One outstanding assessment per learning scope prevents stale-cycle outcomes.
        IF EXISTS(SELECT 1 FROM public.assessment_sessions WHERE user_id=p_user_id AND learning_session_id=learning.session_id
            AND (status='READY' OR (status='SUBMITTED' AND mastery_applied_at IS NULL))) THEN
            RAISE EXCEPTION 'Assessment finalization pending' USING ERRCODE='23505';
        END IF;
        IF p_payload->>'reassessment_job_id' IS NULL AND EXISTS(SELECT 1 FROM public.concept_mastery m
            WHERE m.user_id=p_user_id AND m.learning_session_id=learning.session_id
            AND m.concept_id IN (SELECT jsonb_array_elements_text(p_payload->'concept_queue'))
            AND m.mastery_state IN ('REMEDIATING','REASSESSING','NEEDS_SUPPORT')) THEN
            RAISE EXCEPTION 'Learning progression unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    IF p_action='create' AND p_payload->>'reassessment_job_id' IS NOT NULL THEN
        SELECT * INTO job FROM public.remediation_jobs WHERE remediation_job_id=p_payload->>'reassessment_job_id'
            AND user_id=p_user_id AND learning_session_id=learning.session_id
            AND source_id=learning.source_id AND source_version=learning.source_version FOR UPDATE;
        IF job.remediation_job_id IS NULL OR job.status<>'READY' OR job.metadata->>'completed' IS DISTINCT FROM 'true'
           OR NOT EXISTS(SELECT 1 FROM public.concept_mastery m WHERE m.user_id=p_user_id AND m.learning_session_id=learning.session_id
                AND m.concept_id=job.concept_id AND m.mastery_state='REASSESSING' AND m.remediation_attempt_count=job.attempt_number)
           OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'concept_queue') c(id) WHERE id<>job.concept_id) THEN
            RAISE EXCEPTION 'Reassessment unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    IF p_action='submit' AND assessment.reassessment_job_id IS NOT NULL THEN
        IF NOT EXISTS(SELECT 1 FROM public.remediation_jobs j JOIN public.concept_mastery m
            ON m.user_id=j.user_id AND m.learning_session_id=j.learning_session_id AND m.concept_id=j.concept_id
            WHERE j.remediation_job_id=assessment.reassessment_job_id AND j.user_id=p_user_id
            AND m.mastery_state='REASSESSING' AND m.remediation_attempt_count=j.attempt_number)
            AND assessment.status<>'SUBMITTED' THEN
            RAISE EXCEPTION 'Reassessment unavailable' USING ERRCODE='22023';
        END IF;
    END IF;
    result := visualai_internal.assessment_transaction_phase9(p_action,p_user_id,p_assessment_id,p_payload);
    IF p_action='create' AND p_payload->>'reassessment_job_id' IS NOT NULL THEN
        UPDATE public.assessment_sessions SET assessment_type='REASSESSMENT',reassessment_job_id=job.remediation_job_id WHERE session_id=p_assessment_id AND user_id=p_user_id;
        result := visualai_internal.assessment_transaction_phase9('load',p_user_id,p_assessment_id,'{}');
    ELSIF p_action='submit' THEN
        UPDATE public.assessment_attempts a SET assessment_type=s.assessment_type FROM public.assessment_sessions s
            WHERE a.session_id=s.session_id AND a.user_id=s.user_id AND s.session_id=p_assessment_id AND s.user_id=p_user_id;
    END IF;
    RETURN result;
END $$;
CREATE OR REPLACE FUNCTION public.visualai_assessment_transaction(p_action text,p_user_id uuid,p_assessment_id text,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
    SELECT visualai_internal.assessment_transaction(p_action,p_user_id,p_assessment_id,p_payload)
$$;
REVOKE ALL ON FUNCTION visualai_internal.assessment_transaction_phase9(text,uuid,text,jsonb),visualai_internal.assessment_transaction(text,uuid,text,jsonb),
    public.visualai_assessment_transaction(text,uuid,text,jsonb) FROM PUBLIC,anon,authenticated;
-- Old implementation has no direct service_role grant: only the scoped wrapper may invoke it.
REVOKE ALL ON FUNCTION visualai_internal.assessment_transaction_phase9(text,uuid,text,jsonb) FROM service_role;
GRANT EXECUTE ON FUNCTION visualai_internal.assessment_transaction(text,uuid,text,jsonb),public.visualai_assessment_transaction(text,uuid,text,jsonb) TO service_role;
COMMIT;
