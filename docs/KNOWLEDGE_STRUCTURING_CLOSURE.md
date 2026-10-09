# Knowledge structuring reliability closure — acceptance incomplete

Branch: phase10-mastery-remediation. Existing uncommitted learner-loop work preserved; no commit/push/reset. No frontend, model/routing, Worker deployment, secret, billing, or database-schema changes in this task.

## Evidence and root cause

Existing source SRC_ad3e1c3e2ba85259ac5346396fc80abe resolved by owner JWT to version1, FAILED; knowledge LEGACY_UNMAPPED. One canonical visual unitCU_a0e0a1bb63be5cd3af0f21f7ae64e347, independently VERIFIED. Original JOB_16cff9ede6d2 raw model proposals were not retained by the previously running backend; exact original proposed label/selected anchor cannot be recovered and are not fabricated here.

Deterministic source replay proved one literal verified heading(ref94453de51028;67characters) occurred verbatim in canonical text but crossed sentence boundaries. Original20sentence anchors supplied no complete supporting heading anchor. Whole-unit literal supporttrue, maximumsingleanchor11of13words. Added scope-bound whole-claim spans;33anchors now provide complete support. Original sentence IDs remain stable. This proves an anchor-granularity defect, not an independent visual-verification failure.

ExactlyONE normal-owner POST /sources/SRC_ad3e1c3e2ba85259ac5346396fc80abe/retry-index was made after initial deterministic gates passed. Cloud content_understanding and structure_repair both transportSUCCESS (~23.406s/~25.329s); finalHTTP422 after51.94s. Both actual saved proposals rejected concept labelref274e53097698 at selectedEA_f361e9c4fa415d4585b66a9f08fd0ce5. Selectedquote failed existingderivedlabel support; another source anchorEA_89206be19f155135b7d3323c5a46a20c had word support, but no accepted inventory claim had literal support for the model's annotation. Do NOT conflate word overlap with independently accepted label identity or silently reinterpret this rejected claim. Safe finaldiagnostic UNSUPPORTED_EVIDENCE/LABEL, CONCEPT, HALLUCINATED_LABEL, repair_attemptedtrue. Exact rejected labels/proposals and source text retained privately outside repository in structuring_closure_rejected_private.json / learner_private_provider_*.json; never print raw artifacts.

## Generalized implementation

Typed owner/source/version-scoped inventory distinguishes heading, literal text, component, flowchart label, table header/cell, graph axis/legend, equation, symbol, directed relationship. All entries resolve to literal persisted spans; missing renderer support fails closed. New whole-claim anchors preserve exact characters and existing sentence IDs. Deduplicated bounded scanning shares the existing anchor resource limit4096; no truncation or cardinality-one policy.

Binding is mechanical, source scoped and unambiguous at the minimal supporting span; it never repairs foreign anchor identity or factual relationships. Numeric values/operators/arrows/formula case remain significant. Presentation numbering, bullets, Unicode whitespace and bold display wrappers normalize separately from unchanged evidence. Native explicit numbered outline support also accepts selectable-text PDF; visual renderer headings never establish native outline authority. Organizational support never creates prerequisites.

Failed real retry exposed the additional unconstrained-output-vocabulary defect. After that failed retry, entirely VERIFIED visual sources now constrain model response title/name enums to the accepted scoped inventory. The same vocabulary is enforced server-side even if a provider ignores its schema. Per-request ContextVar schema isolation resets on success/error. This final vocabulary fix has deterministic regression coverage but NOsecondliveacceptance; sourceREADY must not be claimed.

Safe SourceFailure retains failed object type, reason category, label hash and repair_attempted. Existing maximum2proposals and full quote/scope/hierarchy/definition/prerequisite/chunk validation retained. Explicit generic headings allowed only with actual accepted source authority; invented generic placeholders still rejected.

## Tests and real result

Targeted final groups:285passed43skipped. Newmatrix44passed. Coverage: plain/short/multisection TXT and nativePDF; explicit heading-rich TXT/PDF; selectable text and separately verified figures; printed/handwriting/dense technical/flowchart/table/equation/graph sources; multipanel and irrelevant UI data. Negative invented/reordered label, wrong/foreign/version anchor, malformed/empty evidence, hallucinated definition, unsupported prerequisite, reversed visual edge, contradictory graph axes, mathematical/chemical/unit identity and injection cases. Fixtures use existing independent oracle/outline/prose helpers; no pixel-browser claim.

Finalfast verifierPASS(selectedPython contracts/frontend/Worker/strictJS/whitespace). Full regression NOT_RUN for this closure: PhaseG explicitly requires realacceptance to pass first. Previous task full-suite results are not relabeled as a fresh pass.

CloudauthPASS: configuredURL matches speedrun2/currentaccount; deployed228ddfe7-36f7-4286-99b2-ae81d7473898(100%); authenticated no-inference malformedprobe400(payloadvalidation), not401; two actualcloudstructuringcallsSUCCESS. No Worker or credential mutation.

Post-terminationrestart check: ownerknowledgeGET200 returnsLEGACY_UNMAPPED,0topics0subtopics0concepts; sourceFAILED/version1. Filehash and all canonicalContentUnits unchanged. NormalB source/knowledgeGET404/404. PreviousacceptedREADYsource intact. ScopedQdrant count0; indexing never reached because structurefailed. No fake completed state or newly published knowledge. Desired READY/restart-retrieval/sessionQA acceptance NOTRUN because this source has no accepted hierarchy.

## Remaining gate

KNOWLEDGE_STRUCTURING_RELEASE_GATE: FAIL. Required real sourceREADY/knowledgeREADY/acceptedvectorpublication/sessionQA have not succeeded. The single authorized retry allowance was consumed before the final closed-vocabulary fix; no second retry or further inference was made. Final code is prepared and offline gates pass, but live post-fix acceptance and consequent fullregression remain pending. No production-readiness claim.

## Files changed by this closure

- app/services/verified_inventory.py
- app/services/evidence_anchors.py
- app/services/content_understanding.py
- app/services/structurer.py
- app/services/outline_evidence.py
- app/services/ingestion/failures.py
- app/services/ingestion/source_ingestion.py
- tests/test_verified_inventory.py
- tests/test_visual_knowledge_preparation.py
- scripts/verify_changed.py
- docs/KNOWLEDGE_STRUCTURING_CLOSURE.md
- docs/AUTONOMOUS_LEARNER_LOOP_PROGRESS.md
