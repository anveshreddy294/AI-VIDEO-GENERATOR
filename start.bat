@echo off
title VisualAI Server Launcher
echo ========================================================
echo               VisualAI - Starting Services
echo ========================================================
echo.

REM Try starting the Qdrant container if Docker is running
docker start qdrant >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Qdrant Docker container is running.
) else (
    echo [INFO] Docker container not active or not needed.
    echo        VisualAI will use embedded on-disk storage or connect if ready.
)

echo.
echo [OK] Starting FastAPI backend on http://127.0.0.1:8000 ...
echo [INFO] Swagger UI available at: http://localhost:8000/docs
echo [INFO] Press CTRL+C to stop the server at any time.
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
