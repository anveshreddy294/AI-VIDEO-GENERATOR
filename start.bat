@echo off
title VisualAI Server Launcher
echo ========================================================
echo               VisualAI - Starting Services
echo ========================================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found.

REM --- Check/Install venv ---
if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated.

REM --- Install dependencies ---
echo [SETUP] Installing/updating dependencies...
pip install -q -r requirements.txt

REM --- Check .env ---
if not exist ".env" (
    echo [SETUP] No .env found — copying from .env.example
    copy .env.example .env >nul
    echo [ACTION] Edit .env and add your GEMINI_API_KEY before uploading files.
)

REM --- Check FFmpeg ---
where ffmpeg >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] FFmpeg found.
) else (
    echo [WARN] FFmpeg not found — video uploads will fail.
    echo        Install: https://ffmpeg.org/download.html
)

REM --- Try Docker Qdrant ---
docker ps --format "{{.Names}}" 2>nul | findstr /i "visualai-qdrant" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Qdrant Docker container is running.
) else (
    docker start visualai-qdrant >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [OK] Started existing Qdrant container.
    ) else (
        echo [INFO] No Qdrant container. Using embedded on-disk storage.
    )
)

REM --- Start server ---
echo.
echo [OK] Starting FastAPI backend on http://127.0.0.1:8000 ...
echo [INFO] Dashboard:      http://localhost:8000
echo [INFO] Swagger UI:     http://localhost:8000/docs
echo [INFO] Health Check:   http://localhost:8000/health
echo [INFO] Press CTRL+C to stop.
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
