#!/usr/bin/env bash
# VisualAI — Cross-platform start script (macOS / Linux)
set -e

echo "========================================================"
echo "              VisualAI - Starting Services"
echo "========================================================"
echo ""

# --- Check Python ---
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "[OK] Python: $($PYTHON --version 2>&1)"

# --- Check/Install venv ---
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# Activate venv
source .venv/bin/activate
echo "[OK] Virtual environment activated"

# --- Install dependencies ---
echo "[SETUP] Installing/updating dependencies..."
pip install -q -r requirements.txt

# --- Check .env ---
if [ ! -f ".env" ]; then
    echo "[SETUP] No .env found — copying from .env.example"
    cp .env.example .env
    echo "[ACTION] Edit .env and add your GEMINI_API_KEY before uploading files."
fi

# --- Check FFmpeg ---
if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "[WARN] FFmpeg not found — video uploads will fail."
    echo "       Install: brew install ffmpeg (macOS) | sudo apt install ffmpeg (Linux)"
fi

# --- Try Docker Qdrant ---
if command -v docker &>/dev/null; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "visualai-qdrant"; then
        echo "[OK] Qdrant Docker container is running."
    elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "visualai-qdrant"; then
        docker start visualai-qdrant 2>/dev/null && echo "[OK] Started existing Qdrant container." || true
    else
        echo "[INFO] No Qdrant container found. Using embedded on-disk storage."
    fi
else
    echo "[INFO] Docker not available. Using embedded on-disk Qdrant storage."
fi

# --- Start server ---
echo ""
echo "[OK] Starting FastAPI backend on http://127.0.0.1:8000 ..."
echo "[INFO] Dashboard:      http://localhost:8000"
echo "[INFO] Swagger UI:     http://localhost:8000/docs"
echo "[INFO] Health Check:   http://localhost:8000/health"
echo "[INFO] Press CTRL+C to stop."
echo ""

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
