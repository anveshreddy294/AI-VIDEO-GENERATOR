# Phase 7A.3B acceptance

Moondream is removed from normal production extraction and triage. Diagnosis found valid JSON with the unexpected `VISIBLE_EVIDENCE` field, not an envelope problem. A compact 760-character prompt produced schema-valid visual-v2 in 3/3 calls but passed the deterministic quality gate in 0/3: ordinary labels appeared as formulas. No synthetic fields or JSON repair were added.

The native API supports `reasoning`, `max_tokens`, and model-specific `question`; it does not expose `response_format`. See [Cloudflare native input schema](https://developers.cloudflare.com/workers-ai/models/moondream3.1-9B-A2B/schema-input.json). Reasoning was false throughout; the measured prompt/output reduction is not proof of a causal reasoning-setting improvement. The 700x240 fixture transported 15,706 encoded characters. Original prompt: 3,815 characters; answer: 5,289 characters; inference 16,333ms; request 23,147ms. Compact prompt inference: 3,063/1,652/1,724ms; requests: 3,922/1,871/1,944ms. Cold/warm state is unknown.

Triage completed 8/8 requests but passed expected semantic/complexity/flag assertions in 0/8. It repeatedly reported every special flag true. Inference was 957-1,796ms; request latency 1,042-2,183ms. Production deterministic selection measured a 0.0022ms median over 1,000 local selections. Triage adds latency without demonstrated selection improvement; it is not persisted as canonical evidence.

The canonical benchmark completed 16 attempts (Gemma/Qwen x eight fixtures), preserving both timeouts. Quality gate: valid visual-v2, all existing critical fixture assertions, and no conservative unsupported-content flag. These vocabulary flags are conservative review signals, not proof of hallucination. Five of eight cases qualified for each provider. Neither flowchart output passed the conservative flag gate; both complex diagram calls timed out. No flags were removed to manufacture winners.

| Workload | Selected provider | Request seconds | Qualified operational chain |
|---|---|---:|---|
| Printed/OCR | Gemma | 23.992 | Gemma -> Ollama |
| Simple diagram (same printed fixture) | Gemma | 23.992 | Gemma -> Ollama |
| Handwriting | Qwen | 9.668 | Qwen -> Gemma -> Ollama |
| Graph axes | Qwen | 39.572 | Qwen -> Ollama |
| Table | Qwen | 17.039 | Qwen -> Gemma -> Ollama |
| Equation | Qwen | 15.474 | Qwen -> Gemma -> Ollama |
| Flowchart | No qualified provider | - | Fail before provider invocation |
| Explicit COMPLEX | No qualified provider | - | Fail before provider invocation |

These are individual measurements, not cold/warm estimates or repeated-provider averages. The diagram shares the printed fixture; the graph fixture checks axes text, not plotted digitization. Unclassified inputs use conservative Gemma selection, without claiming automatic semantic classification. Relationship threshold eight was removed because the fixtures cannot calibrate it.

Production model failures may advance only through the qualified finite operational chain. Detected quality/schema failures do not advance. Existing visual-v2, sanitizer, prompt-injection protections and exact Gemma identity mapping remain intact. Generic schema validation is not exhaustive source grounding: the Moondream formula labels passed it and were rejected by fixture-specific evaluation. Phase 7B verification/repair was not implemented.

Worker `speedrun` redeployed as `5d9c8da7-c0ec-4de9-9e1d-829227e734dc`; initial deployment `baeec9c3-95e1-49b8-95c7-801120b81090`; rollback anchor `da6b3c6f-c633-450b-a773-376f2263bf2d`. The account and API_KEY secret name were checked. Worker source was unchanged in this phase; backend routing and measurement tooling changed. All seven text tasks and health passed. Local backend restarted and health returned 200 with Cloudflare enabled.

Validation: 59 Worker tests, 106 targeted Python tests, 21 frontend tests; full suite 1,010 passed, one skipped, four existing warnings, 217.00s. Dry run and diff check passed. No migrations, canonical application writes, Qdrant changes, embedding changes, commit, or push. Coverage remains partial; flowchart and complex workloads block complete calibration and readiness.
