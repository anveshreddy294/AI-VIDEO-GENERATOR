# Existing learning API fixes

This change repairs the current educational lesson workflow. It does not add
interest onboarding, new RAG collections, learning loops, mastery automation,
remediation, or reassessment.

## API and browser contracts

- Topic notes accept an optional JSON body containing `detail_level`:
  `concise`, `standard`, or `detailed`. An omitted body remains compatible with
  existing clients. Cached notes are reused only at the requested detail level.
- The browser renders the actual notes fields: `title`, `summary`,
  `key_points`, `key_concepts`, `examples`, and `equations`.
- Assessments expose `mcqs` and one `descriptive` question. Submission requires
  valid answers to those question IDs. Descriptive feedback is a string.
- Descriptive grading uses a structured rubric-based reasoning request. Provider
  or response-validation failures do not save fabricated scores.
- Video clients consume `status`, `stage`, and `progress`. Terminal states are
  `COMPLETED` and `FAILED`. Reload restoration reads the nested `video` object.
- Video playback uses authenticated fetch followed by a browser object URL.
  Navigation clears polling and revokes the object URL. Late responses cannot
  update a different topic workspace.
- Startup and generation failures use safe JSON error codes; internal exceptions
  are logged rather than returned as public error details.
- Topic ASK requests reject empty/excessive input and unwrap JSON answers.
  Generated answers remain AI-enriched even when source observations are supplied.
- Lesson persistence merges changed feature fields under the existing store lock
  to preserve parallel notes, questions, and video updates.

## Providers

`REASONING_PROVIDER` defaults to `LLM_PROVIDER`, whose default is `ollama`.
Set `REASONING_PROVIDER=cloudflare` explicitly for cloud-first text reasoning.
Visual cloud transport remains independent of this text setting.

`VISION_LOCAL_FALLBACK_ENABLED=true` enables the existing bounded Ollama fallback
for operational cloud failures. Authentication rejections and invalid evidence
do not trigger an alternate extraction to bypass validation. Independent visual
verification remains required; successful extraction alone is not publication.

Production video audio uses the configured TTS provider with spoken narration
required. It no longer selects the unrecognized `edge` alias, which previously
fell through to synthetic audio. Audio-service failures become
`VIDEO_AUDIO_FAILED`; test mode may still use synthetic audio explicitly.

## Docker

The pinned Qdrant image has Bash but does not contain `wget` or `curl`. Compose
now checks `/readyz` with Bash's TCP support. The probe was verified against the
running container, whose readiness endpoint returned HTTP 200.

The API container uses `host.docker.internal:11434` to reach host Ollama.
Override `DOCKER_OLLAMA_BASE_URL` when Ollama runs elsewhere. The Dockerfile now
includes Cairo/Pango build prerequisites used by Manim dependencies.

These configuration changes do not alter an already-created container. Container
recreation is needed to replace its stored health-check configuration. No
container restart or image rebuild was performed during this repair.

## Verification scope and remaining limits

Regression coverage includes topic workspace interactions, descriptive assessment
contracts, safe errors, concurrent lesson updates, visual extraction/indexing
boundaries, rendering, and media artifact checks. Live probes confirmed local
Ollama text reasoning and synthetic PNG extraction through local fallback.

The final Python suite completed with 1,454 passed and 137 skipped. Skipped
checks are not evidence of successful production integration.

Upload acceptance tests explicitly separate content extraction from optional
canonical indexing. `CONTENT_READY` must not be presented as indexed `READY`.

The existing lesson store remains local JSON, and video processing remains
in-process. These fixes do not introduce database migrations, a durable task
queue, or multi-host artifact storage. External vision verification and live
spoken TTS availability still depend on their configured services. The user's
original failing PNG was not available for reproduction.
