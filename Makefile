# VisualAI — Cross-platform Makefile
# Works on macOS, Linux, and Windows (with make installed via Git Bash / WSL)

.PHONY: setup run stop clean docker-up docker-down audit test help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv and install dependencies
	python3 -m venv .venv 2>/dev/null || python -m venv .venv
	.venv/bin/pip install -q -r requirements.txt 2>/dev/null || .venv\Scripts\pip install -q -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "[OK] Setup complete. Edit .env to add your GEMINI_API_KEY."

run:  ## Start the development server
	.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 2>/dev/null || \
	.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

stop:  ## Stop any running uvicorn processes
	-pkill -f "uvicorn app.main" 2>/dev/null || taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>/dev/null || true
	@echo "[OK] Server stopped."

clean:  ## Remove venv, caches, and temp files
	rm -rf .venv __pycache__ app/__pycache__ app/*/__pycache__ 2>/dev/null || rmdir /s /q .venv 2>nul
	@echo "[OK] Cleaned."

test:  ## Run the full test suite from the tests/ folder
	.venv/bin/python -m pytest tests/ -v 2>/dev/null || \
	.venv\Scripts\python -m pytest tests/ -v
	@echo "[OK] All tests complete."

test-core:  ## Run the 4 core pipeline tests (fast, no full suite)
	.venv/bin/python -m unittest tests.test_step4_remediation_loop tests.test_video_rag_agent tests.test_instructor_portal tests.test_step2_to_step3_remediation -v 2>/dev/null || \
	.venv\Scripts\python -m unittest tests.test_step4_remediation_loop tests.test_video_rag_agent tests.test_instructor_portal tests.test_step2_to_step3_remediation -v

docker-up:  ## Start with Docker Compose
	docker compose up -d --build
	@echo "[OK] Services started. Dashboard: http://localhost:8000"

docker-down:  ## Stop Docker Compose (preserves data)
	docker compose down
	@echo "[OK] Services stopped."

audit:  ## Run security audit
	.venv/bin/pip-audit 2>/dev/null || .venv\Scripts\pip-audit
