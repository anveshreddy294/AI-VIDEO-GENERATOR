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
        self.qdrant_path: Path = BASE_DIR / os.getenv("QDRANT_PATH", "storage/runtime/qdrant")
        self.collection_name: str = os.getenv("COLLECTION_NAME", "visualai_layer_a_gemini_v1")

        # --- Models ---
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2")
        self.generation_model: str = os.getenv("GENERATION_MODEL", "qwen3:8b")

        # --- Storage Architecture (Separation of Fixtures & Runtime) ---
        self.storage_dir: Path = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
        self.runtime_dir: Path = BASE_DIR / os.getenv("RUNTIME_DIR", "storage/runtime")
        self.include_fixture_sources = os.getenv("INCLUDE_FIXTURE_SOURCES", "false").lower() == "true"
        self.assessment_pass_threshold = float(os.getenv("ASSESSMENT_PASS_THRESHOLD", "70"))
        self.fixtures_dir: Path = BASE_DIR / os.getenv("FIXTURES_DIR", "tests/fixtures")
        self.registry_dir: Path = BASE_DIR / os.getenv("REGISTRY_DIR", "storage/runtime/registry")
        env_upload = os.getenv("UPLOAD_DIR")
        self.upload_dir: Path = BASE_DIR / env_upload if (env_upload and env_upload != "storage/uploads") else self.runtime_dir / "uploads"

        env_processed = os.getenv("PROCESSED_DIR")
        self.processed_dir: Path = BASE_DIR / env_processed if (env_processed and env_processed != "storage/processed") else self.runtime_dir / "processed"

        self.video_targets_dir: Path = BASE_DIR / os.getenv("VIDEO_TARGETS_DIR", "storage/runtime/video_targets")

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.video_targets_dir.mkdir(parents=True, exist_ok=True)

        # --- File validation ---
        self.allowed_extensions: set[str] = set(
            os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,txt,mp4,mov,mkv").split(",")
        )
        # JPEG arrives as .jpg or .jpeg — normalize to the set above.

        # --- Video Matrix ---
        self.video_extensions: set[str] = {"mp4", "mov", "mkv"}
        self.frame_interval_seconds: int = int(os.getenv("FRAME_INTERVAL_SECONDS", "12"))
        self.whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
        # Frames whose mean pixel difference vs the previous kept frame is
        # *below* this threshold are treated as duplicates and skipped.
        self.video_frame_similarity_threshold: float = float(
            os.getenv("VIDEO_FRAME_SIMILARITY_THRESHOLD", "0.04")
        )

        # --- Chunking / RAG ---
        self.chunk_size: int = 1000  # tokens, per the Layer A spec
        self.chunk_overlap: int = 150

        # --- Step 2: Assessment ---
        self.assessment_dir: Path = BASE_DIR / os.getenv("ASSESSMENT_DIR", "storage/runtime/assessment_sessions")
        self.assessment_dir.mkdir(parents=True, exist_ok=True)
        self.learning_profiles_dir: Path = BASE_DIR / os.getenv("LEARNING_PROFILES_DIR", "storage/runtime/learning_profiles")
        self.learning_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.max_questions: int = int(os.getenv("MAX_QUESTIONS", "10"))
        self.assessment_ttl_hours: int = int(os.getenv("ASSESSMENT_TTL_HOURS", "24"))
        self.max_question_retries: int = int(os.getenv("MAX_QUESTION_RETRIES", "2"))
        self.mastery_threshold: int = int(os.getenv("MASTERY_THRESHOLD", "2"))
        self.kill_switch_limit: int = int(os.getenv("KILL_SWITCH_LIMIT", "3"))
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        self.ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))

    # ---------- Validation helpers ----------
    def is_allowed(self, filename: str) -> bool:
        ext = Path(filename).suffix.lstrip(".").lower()
        return ext in self.allowed_extensions

    def require_gemini(self) -> None:
        """Ensure Gemini API credentials exist."""
        if not self.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your .env file."
            )


settings = Settings()