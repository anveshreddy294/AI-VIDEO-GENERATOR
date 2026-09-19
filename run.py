"""VisualAI — Cross-platform runner with safe reloading.

Ensures Uvicorn auto-reload monitors only the `app/` directory and explicitly ignores
virtual environments (`.venv/`), runtime storage (`storage/`), and temporary caches.
"""

from pathlib import Path
import uvicorn

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    app_dir = root_dir / "app"
    venv_dir = root_dir / ".venv"
    storage_dir = root_dir / "storage"

    print("========================================================")
    print("              VisualAI - Starting Services")
    print("========================================================")
    print(f"[INFO] Watch directory:  {app_dir}")
    print(f"[INFO] Excluded dirs:    {venv_dir}, {storage_dir}")
    print("[INFO] Dashboard:        http://127.0.0.1:8000")
    print("[INFO] Swagger UI:       http://127.0.0.1:8000/docs")
    print("[INFO] Health Check:     http://127.0.0.1:8000/health")
    print("[INFO] Press CTRL+C to stop.")
    print("========================================================")

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(app_dir)],
        reload_excludes=[str(venv_dir), str(storage_dir)],
    )
