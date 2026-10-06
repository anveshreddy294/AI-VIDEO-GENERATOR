BEGIN;
CREATE INDEX sources_current_version_fk_idx ON public.sources (user_id, source_id, version, source_version);
COMMIT;
