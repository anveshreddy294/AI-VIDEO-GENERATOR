BEGIN;
CREATE SCHEMA IF NOT EXISTS visualai_internal;
REVOKE ALL ON SCHEMA visualai_internal FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA visualai_internal TO authenticated;

-- Direct table writes remain denied. These private definers are the limited write boundary.
-- Public invoker wrappers expose only these operations, never arbitrary SQL or owner IDs.
CREATE FUNCTION visualai_internal.commit_source_ingestion(p_source jsonb, p_version jsonb, p_units jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $function$
DECLARE
    caller uuid := auth.uid();
    source_key text := p_source->>'source_id';
    version_number integer := (p_source->>'version')::integer;
    existing public.sources;
    existing_version public.source_versions;
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
    SELECT * INTO existing FROM public.sources WHERE source_id=source_key FOR UPDATE;
    IF FOUND AND existing.user_id<>caller THEN
        RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501';
    END IF;
    SELECT * INTO existing_version FROM public.source_versions
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
       SELECT 1 FROM public.sources WHERE source_id=p_source->>'parent_source_id' AND user_id=caller) THEN
       RAISE EXCEPTION 'Parent source unavailable' USING ERRCODE='42501';
    END IF;
    -- Deferred current-version FK is checked at transaction commit after its row exists.
    INSERT INTO public.sources (source_id, user_id, legacy_student_id, asset_id, upload_id, filename, source_type, mime_type, file_hash, file_size, version, source_version, title, sha256, parser_version, sanitization_version, parent_source_id, status, error_message) SELECT r.source_id, r.user_id, r.legacy_student_id, r.asset_id, r.upload_id, r.filename, r.source_type, r.mime_type, r.file_hash, r.file_size, r.version, r.source_version, r.title, r.sha256, r.parser_version, r.sanitization_version, r.parent_source_id, r.status, r.error_message FROM pg_catalog.jsonb_populate_record(NULL::public.sources, p_source) r;
    INSERT INTO public.source_versions (user_id, source_id, version, source_version, file_hash, sha256, filename, file_location, provenance, normalized_content, sanitized_content, quarantined_content, rich_chunks, topic_blueprint) SELECT r.user_id, r.source_id, r.version, r.source_version, r.file_hash, r.sha256, r.filename, r.file_location, r.provenance, r.normalized_content, r.sanitized_content, r.quarantined_content, r.rich_chunks, r.topic_blueprint FROM pg_catalog.jsonb_populate_record(NULL::public.source_versions, p_version) r;
    INSERT INTO public.content_units (user_id, source_id, source_version, content_id, asset_id, layer, modality, text, visual_description, page_number, page_start, page_end, slide_number, timestamp_start, timestamp_end, speaker, heading_path, frame_id, sequence_index, chapter, section, parent_content_id, char_start, char_end, line_start, line_end, bbox, region_id, image_id, image_path, extraction_method, confidence_score, provenance) SELECT r.user_id, r.source_id, r.source_version, r.content_id, r.asset_id, r.layer, r.modality, r.text, r.visual_description, r.page_number, r.page_start, r.page_end, r.slide_number, r.timestamp_start, r.timestamp_end, r.speaker, r.heading_path, r.frame_id, r.sequence_index, r.chapter, r.section, r.parent_content_id, r.char_start, r.char_end, r.line_start, r.line_end, r.bbox, r.region_id, r.image_id, r.image_path, r.extraction_method, r.confidence_score, r.provenance FROM pg_catalog.jsonb_populate_recordset(NULL::public.content_units, p_units) r;
    RETURN (SELECT to_jsonb(s) FROM public.sources s WHERE s.source_id=source_key AND s.user_id=caller);
END;
$function$;

CREATE FUNCTION visualai_internal.source_index_status(p_source_id text, p_version integer, p_status text, p_error text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $function$
DECLARE
    caller uuid := auth.uid();
    result jsonb;
BEGIN
    IF caller IS NULL THEN RAISE EXCEPTION 'Authenticated identity required' USING ERRCODE='42501'; END IF;
    IF p_status IS NULL OR p_status NOT IN ('INDEXING','READY','FAILED')
       OR (p_status='FAILED' AND coalesce(p_error,'')='') THEN
        RAISE EXCEPTION 'Invalid indexing status';
    END IF;
    UPDATE public.sources s SET status=p_status, error_message=CASE WHEN p_status='FAILED' THEN p_error ELSE NULL END
      WHERE s.source_id=p_source_id AND s.user_id=caller AND s.version=p_version
      AND EXISTS (SELECT 1 FROM public.source_versions v WHERE v.source_id=s.source_id AND v.user_id=caller AND v.version=p_version)
      RETURNING to_jsonb(s) INTO result;
    IF result IS NULL THEN RAISE EXCEPTION 'Source unavailable' USING ERRCODE='42501'; END IF;
    RETURN result;
END;
$function$;

REVOKE ALL ON FUNCTION visualai_internal.commit_source_ingestion(jsonb,jsonb,jsonb) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION visualai_internal.source_index_status(text,integer,text,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION visualai_internal.commit_source_ingestion(jsonb,jsonb,jsonb) TO authenticated;
GRANT EXECUTE ON FUNCTION visualai_internal.source_index_status(text,integer,text,text) TO authenticated;

CREATE FUNCTION public.visualai_commit_source_ingestion(p_source jsonb, p_version jsonb, p_units jsonb)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path = '' AS $function$
    SELECT visualai_internal.commit_source_ingestion(p_source, p_version, p_units);
$function$;
CREATE FUNCTION public.visualai_source_index_status(p_source_id text, p_version integer, p_status text, p_error text DEFAULT NULL)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path = '' AS $function$
    SELECT visualai_internal.source_index_status(p_source_id,p_version,p_status,p_error);
$function$;
REVOKE ALL ON FUNCTION public.visualai_commit_source_ingestion(jsonb,jsonb,jsonb) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.visualai_source_index_status(text,integer,text,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.visualai_commit_source_ingestion(jsonb,jsonb,jsonb) TO authenticated;
GRANT EXECUTE ON FUNCTION public.visualai_source_index_status(text,integer,text,text) TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
