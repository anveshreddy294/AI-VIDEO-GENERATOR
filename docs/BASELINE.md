# Merged archive baseline

14 September 2026. Source: AICARLS-MERGED-WITH-CODEX-FIXES.zip.

| Check | Observed result |
|---|---|
| Backend | 29 passed |
| Frontend build | Passed |
| Frontend lint | 52 errors |
| Docker image build | Passed, aicarls-merged-baseline |
| Isolated Compose | Started on ports 3002 / 5002 |
| /api/health | HTTP 200 |
| /api/pageindex/health | HTTP 200; body/index quality not implied |
| Deterministic semantic verification | Passed, real Piper/Manim/FFmpeg, 11.19 seconds |
| Live chat | HTTP 503; provider authentication failure |
| Full live lesson | Not attempted with the known failing credential |

Baseline render used the curated verification plan, not live model planning.
