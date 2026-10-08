# Phase 10 backend contract

The existing MasteryStateMachine, MasteryRecord, AssessmentAttempt, MisconceptionEvidence and RemediationJob drive the canonical loop. Legacy video orchestration is untouched and stays blocked in Supabase mode.

## API

All routes use verified identity and the existing `/learning-sessions` family:

- GET `/{session_id}/mastery`: concept records, weak concepts, conservative gaps, evidence-backed remediation, eligible reassessment job IDs and human fallback.
- POST `/{session_id}/mastery/finalize`: only `{ "assessment_id": "..." }`; derives outcomes from persisted Phase 9 attempts.
- POST `/{session_id}/remediation/{job_id}/complete`: empty body; acknowledges review, grants reassessment eligibility, never grants mastery.
- POST `/{session_id}/remediation/{job_id}/reassessment`: existing Phase 9 SessionAssessmentRequest. Returns SafeQuestion. Submit and retrieve results through the existing Phase 9 routes, then finalize that assessment.

Anonymous requests are 401; foreign scope is safe 404; extra caller authority fields are 422. Storage failure is explicit, with no memory or file fallback. No answer keys leave the aggregate repository.

## Policy

Canonical diagnostic proof uses `settings.mastery_threshold` (existing correct streak, default two); score boundaries remain MasteryConfig 80/60. Reassessment reuses the existing two-attempt threshold. The existing `settings.kill_switch_limit` defaults to three remediation cycles, after which NEEDS_SUPPORT persists and blocks the automated loop. Scores, counters and streaks update once per canonical attempt. Unrelated mastery remains unchanged. Generic gaps retain POSSIBLE confidence and never claim a learner belief.

Plans use central RetrievalService exact retrieval, pinned to owner, LearningSession and source version. They contain weak target, supported weak prerequisites, reason, evidence/content references and acknowledgement state. No video, model or direct vector access is added. The existing metadata JSON field is a compatibility constraint; GroundedRemediationPlan validates a bounded typed payload. A named twenty-concept/evidence budget matches the retrieval contract; database aggregate payloads have a 1024-row safety bound.

## Persistence / deployment

`20261008120000_session_mastery.sql`: READY_TO_APPLY, after the unapplied Phase 9 `20261008090000_session_assessments.sql`. Never deploy automatically.

Adds nullable LearningSession links to existing mastery/gap/remediation tables, separate unique scopes preserving historical records, diagnostic streak, revision and finalization journal. Atomic service-role-only RPCs lock the learning scope, compare revision and commit derived records plus journal together. A wrapper retains Phase 9 generation/grading and tags authorized reassessment attempts; only one outstanding assessment per LearningSession is permitted to prevent stale-cycle outcomes. Backend verified context supplies owner; no public invocation or new Auth/RLS policy is added.

Legacy learning_profiles remain version-scoped; the frontend reads the canonical session aggregate rather than writing a conflicting profile mirror.

Real PostgreSQL execution and grants are DEFERRED_INFRASTRUCTURE unless the existing disposable test runtime is available. Repository HTTP contracts and deterministic tests are offline. Remote schema deployment and the full Phase 9 + 10 regression gate remain separate.
