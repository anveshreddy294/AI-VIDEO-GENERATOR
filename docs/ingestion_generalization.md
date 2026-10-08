# Generalized source ingestion

## Admission and encoding truth

HTTP admission and canonical ingestion share `inspect_upload`. JPEG, PNG and
single-frame WEBP are decoded and checked before a job is created. The original
filename is metadata; the stored extension and MIME follow decoded bytes. Safe
image suffix/browser-MIME disagreements are normalized. Corrupt, unsupported,
uniform/empty, oversized and incompatible bytes receive fixed validation codes.
GIF/animated images are deliberately unsupported. Image limits remain 8 MiB and
16 megapixels. Format provenance contains no filesystem paths.

## Publication and retry

The existing `visualai_commit_source_ingestion` RPC remains the atomic
source/version/ContentUnit transaction. Knowledge must be READY before indexing;
source READY follows successful indexing. READY retries perform no inference or
vector writes. A lost READY acknowledgement is reconciled using the same owned
source identity. Cancelling an asyncio wrapper cannot stop its thread: source
jobs wait for the bounded worker's actual outcome before declaring a terminal
state. Refresh reads canonical source state.

The public job `source_lifecycle` exposes UPLOADED, EXTRACTING, VERIFYING,
PERSISTING, STRUCTURING, INDEXING, READY and FAILED. The deployed database enum
is unchanged: INDEXING is its durable pre-READY checkpoint while knowledge/index
publication proceeds. Job tracking remains in process; canonical reads survive
server restart, while historical job IDs do not become a durable job ledger.

## Independent visual review bounds

Runtime verification has no known-image hash oracle. The old fixture oracle is
explicitly injected by pytest only; the acceptance matrix restores the production
source-check implementation and mocks the external review transport separately.

Review uses at most 16 distinct claims per request, 24 batches and three concurrent
requests across regions. These named limits bound output size, cost and fan-out;
they are resource policy, not image-specific thresholds. The existing shared
deadline remains authoritative. Prompts are bounded to 32,000 characters.
Exhausted budgets remain UNCERTAIN. Repeated-panel detection supports 2–8 panels
using repeated footer geometry, not filenames, headings or a three-slide count.
Ambiguous layouts remain whole images and use bounded claim review.

Only independently VERIFIED claims may publish. The existing sufficient-evidence
and atomic graph/table checks still apply to subset publication. READY does not
promise every claim in a complex input was readable or accepted. There is no
automatic repair, self-verification or conversion of UNCERTAIN to VERIFIED.

## Acceptance evidence (2026-10-09)

`tests/test_ingestion_acceptance_matrix.py` covers twelve positive input classes
and five early-negative classes through HTTP, terminal jobs, canonical knowledge,
index publication and RetrievalService. Provider, Data API and vector doubles are
explicit; this is contract evidence rather than real-model accuracy evidence.
Additional regressions cover more than 128 claims, review capacity, two/four/five/
eight panels, READY idempotence, cancellation, and lost publication acknowledgement.

Exactly two new real uploads were made:

| Class | Job | Source / knowledge | Indexed points | Verified claims |
| --- | --- | --- | --- | --- |
| Dense JPEG diagram | JOB_89fcddcdf3e2 SUCCEEDED | READY / READY | 3 | 59 |
| WEBP bytes named PNG | JOB_511fd3c33cac SUCCEEDED | READY / READY | 2 | 17 |

Both have authenticated semantic retrieval READY and grounded canonical concept
names. Both use verified-subset publication; neither publishes uncertain or
rejected claims. Existing TXT, simple-image and multi-panel sources were read
back with READY knowledge and working retrieval, without another ingestion.

No Worker deployment, migration, model-routing change, commit or push was made
for this task. The single full regression returned 1260 passed, 137 skipped and
two legacy blank-fixture failures. Their setup now uses a real nonblank fixture;
the affected rate-limit file passes all three tests. No second full run was made.
