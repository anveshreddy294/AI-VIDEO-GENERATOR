"""Central configuration for VisualAI — loads env vars and validates them."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        # --- API keys & services ---
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
        self.qdrant_path: Path = BASE_DIR / os.getenv("QDRANT_PATH", "storage/qdrant")
        self.collection_name: str = os.getenv("COLLECTION_NAME", "visualai_layer_a")

        # --- Models ---
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
        self.generation_model: str = os.getenv("GENERATION_MODEL", "gemini-2.5-flash")

        # --- Storage ---
        self.upload_dir: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "storage/uploads")
        self.processed_dir: Path = BASE_DIR / os.getenv("PROCESSED_DIR", "storage/processed")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # --- File validation ---
        self.allowed_extensions: set[str] = set(
            os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,txt,mp4,mov,mkv").split(",")
        )
        # JPEG arrives as .jpg or .jpeg — normalize to the set above.

        # --- Video Matrix ---
        self.video_extensions: set[str] = {"mp4", "mov", "mkv"}
        self.frame_interval_seconds: int = int(os.getenv("FRAME_INTERVAL_SECONDS", "12"))
        self.whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base")
        # Frames whose mean pixel difference vs the previous kept frame is
        # *below* this threshold are treated as duplicates and skipped.
        self.video_frame_similarity_threshold: float = float(
            os.getenv("VIDEO_FRAME_SIMILARITY_THRESHOLD", "0.04")
        )

        # --- Chunking / RAG ---
        self.chunk_size: int = 1000  # tokens, per the Layer A spec
        self.chunk_overlap: int = 150

    # ---------- Validation helpers ----------
    def is_allowed(self, filename: str) -> bool:
        ext = Path(filename).suffix.lstrip(".").lower()
        return ext in self.allowed_extensions

    def require_gemini(self) -> None:
        if not self.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
            )


settings = Settings()