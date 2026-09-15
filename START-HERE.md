# AICARLS integrated project

This is the complete current source project: the earlier application plus the connected session knowledge, ingestion, tutor, assessment, gaps and roadmap changes. It is not a patch to apply to the older ZIP. Extract into a new folder; do not run the historical integration/cleanup scripts again.

## Run with Docker Desktop

From the extracted project folder in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open http://localhost:3000 (backend: http://localhost:5000). Stop older AICARLS containers before using these same ports/container names. The standard docker-compose.yml builds from this source; compose.verify.yml is the previous workspace verification configuration and depends on a locally created image.

No credentials are included. External AI setup remains paused. TXT/PDF ingestion and local knowledge behavior can run without provider credentials; image recognition, generated tutoring and full lesson planning require provider setup. Assessment requires a completed lesson; the automated closed-loop test simulates that gate explicitly.

Dependencies, cached voice models, generated videos, private session databases, uploads and .env files are excluded. Dependency installation and first-use voice-model downloads require internet access. Bundled source/curriculum assets are retained.

## Verification

See AICARLS-FINAL-STATUS.md for the exact verified scope and limitations. Latest source verification: 58 backend tests, frontend production build, scoped lint and one local deterministic semantic video regression passed. Packaging did not repeat those expensive checks. The production image was not freshly rebuilt in the final verification run.

For backend tests in a configured development environment, install requirements.txt and requirements-dev.txt, then set PYTHONPATH to backend and run `python -m pytest backend/tests -q`. Frontend commands run from frontend: `npm ci` and `npm run build`.

Packaging corrections: the example environment credentials are blank, and run_dev.ps1 now installs the root requirements.txt.
