"""Central configuration for VisualAI — loads env vars and validates them."""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import SecretStr

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        # --- API keys & services ---
        self.qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
        self.qdrant_path: Path = BASE_DIR / os.getenv("QDRANT_PATH", "storage/runtime/qdrant")
        self.requested_collection_name: str = os.getenv("COLLECTION_NAME", "visualai_layer_a_v1").strip()

        # --- Models ---
        self.embedding_model: str = (os.getenv("OLLAMA_EMBED_MODEL") or os.getenv("EMBEDDING_MODEL", "embeddinggemma")).strip()
        self.embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()
        self.embedding_fallback_model: str = os.getenv("EMBEDDING_FALLBACK_MODEL", "embeddinggemma").strip()
        # Retire the two unqualified historical namespaces for the intended model.
        # Never relabel their unknown vectors or silently migrate custom collections.
        semantic_collection = os.getenv("SEMANTIC_COLLECTION_NAME", "").strip()
        legacy_embeddinggemma = (self.embedding_provider == "ollama"
            and self.embedding_model.removesuffix(":latest") == "embeddinggemma"
            and self.requested_collection_name in {"visualai_layer_a", "visualai_layer_a_v1"})
        self.collection_name: str = semantic_collection or (
            "visualai_embeddinggemma_v2" if legacy_embeddinggemma else self.requested_collection_name)
        if not self.collection_name or not all(c.isalnum() or c in "_-" for c in self.collection_name):
            raise ValueError("Collection name must contain only letters, digits, underscores or hyphens")
        self.generation_model: str = os.getenv("GENERATION_MODEL", "llama3.2:3b")

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
            os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,webp,txt,mp4,mov,mkv").split(",")
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
        self.reasoning_provider: str = os.getenv("REASONING_PROVIDER", "cloudflare").strip().lower()
        self.reasoning_local_fallback_enabled = os.getenv("REASONING_LOCAL_FALLBACK_ENABLED", "true").lower() in {"1", "true", "yes"}
        self.ollama_base_url: str = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.ollama_url: str = self.ollama_base_url
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.ollama_embed_model: str = self.embedding_model
        self.ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))

        # Dedicated semantic routing; legacy/vision/video provider selection is unchanged.
        self.cloudflare_worker_url: str = os.getenv("CLOUDFLARE_WORKER_URL", "").strip()
        self.cloudflare_worker_secret: SecretStr = SecretStr(os.getenv("CLOUDFLARE_WORKER_SECRET", ""))
        self.cloudflare_vision_general_model = os.getenv("CLOUDFLARE_VISION_GENERAL_MODEL", "@cf/google/gemma-4-26b-a4b-it")
        self.cloudflare_vision_deep_model = os.getenv("CLOUDFLARE_VISION_DEEP_MODEL", "@cf/qwen/qwen3.8-27b")
        self.cloudflare_connect_timeout: float = float(os.getenv("CLOUDFLARE_CONNECT_TIMEOUT", "10"))
        self.cloudflare_read_timeout: float = float(os.getenv("CLOUDFLARE_READ_TIMEOUT", "180"))
        self.cloudflare_write_timeout: float = float(os.getenv("CLOUDFLARE_WRITE_TIMEOUT", "30"))
        self.cloudflare_overall_timeout: float = float(os.getenv("CLOUDFLARE_OVERALL_TIMEOUT", "300"))
        self.cloudflare_retry_backoff: float = float(os.getenv("CLOUDFLARE_RETRY_BACKOFF", "1"))
        self.cloudflare_max_concurrency: int = int(os.getenv("CLOUDFLARE_MAX_CONCURRENCY", "3"))
        self.cloudflare_max_retries: int = int(os.getenv("CLOUDFLARE_MAX_RETRIES", "1"))
        self.cloudflare_circuit_threshold: int = int(os.getenv("CLOUDFLARE_CIRCUIT_THRESHOLD", "3"))
        self.cloudflare_circuit_cooldown: float = float(os.getenv("CLOUDFLARE_CIRCUIT_COOLDOWN", "60"))

        # --- Step 3: Video Engine Directories & Configuration ---
        self.video_plans_dir: Path = BASE_DIR / os.getenv("VIDEO_PLANS_DIR", "storage/runtime/video_plans")
        self.renders_dir: Path = BASE_DIR / os.getenv("RENDERS_DIR", "storage/runtime/renders")
        self.audio_dir: Path = BASE_DIR / os.getenv("AUDIO_DIR", "storage/runtime/audio")
        self.captions_dir: Path = BASE_DIR / os.getenv("CAPTIONS_DIR", "storage/runtime/captions")

        self.video_plans_dir.mkdir(parents=True, exist_ok=True)
        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.captions_dir.mkdir(parents=True, exist_ok=True)

        self.video_default_fps: int = int(os.getenv("VIDEO_DEFAULT_FPS", "30"))
        self.video_resolution: str = os.getenv("VIDEO_RESOLUTION", "720p")
        self.tts_provider: str = os.getenv("TTS_PROVIDER", "edge_tts").strip().lower()
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "base").strip().lower()
        self.video_timeout: float = float(os.getenv("VIDEO_TIMEOUT", "180.0"))
        self.video_output_dir: Path = BASE_DIR / os.getenv("VIDEO_OUTPUT_DIR", "storage/videos")
        self.video_output_dir.mkdir(parents=True, exist_ok=True)
        self.manim_quality: str = os.getenv("MANIM_QUALITY", "low").strip().lower()
        self.ffmpeg_preset: str = os.getenv("FFMPEG_PRESET", "fast").strip().lower()
        self.pass_threshold: float = self.assessment_pass_threshold
        self.reasoning_model: str = self.ollama_model
        self.qdrant_collection: str = self.collection_name

        # --- Concurrency & Admission Control ---
        self.ollama_max_concurrency: int = int(os.getenv("OLLAMA_MAX_CONCURRENCY", "1"))
        self.video_render_max_concurrency: int = int(os.getenv("VIDEO_RENDER_MAX_CONCURRENCY", "1"))
        self.ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
        self.max_background_jobs: int = int(os.getenv("MAX_BACKGROUND_JOBS", str(self.cloudflare_max_concurrency if self.reasoning_provider == "cloudflare" else self.ollama_max_concurrency)))
        self.max_pending_jobs: int = int(os.getenv("MAX_PENDING_JOBS", "20"))
        self.job_retention_max: int = int(os.getenv("JOB_RETENTION_MAX", "100"))

        # --- Cloud-primary vision with configurable operational local fallback. ---
        self.vision_provider: str = os.getenv("VISION_PROVIDER", "cloudflare").strip().lower()
        self.vision_local_fallback_enabled: bool = os.getenv("VISION_LOCAL_FALLBACK_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
        self.visual_independent_verifier: str = os.getenv("VISUAL_INDEPENDENT_VERIFIER", "none").strip().lower()
        if self.visual_independent_verifier not in ("none", "ollama", "cloudflare"):
            raise ValueError("VISUAL_INDEPENDENT_VERIFIER must be none, ollama or cloudflare")
        self.ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "gemma3:4b").strip()
        self.vision_model: str = (
            os.getenv("VISION_MODEL")
            or os.getenv("OLLAMA_VISION_MODEL")
            or "gemma3:4b"
        ).strip()
        self.vision_fallback_model: str = os.getenv("VISION_FALLBACK_MODEL", "").strip()
        self.vision_timeout_seconds: float = float(os.getenv("VISION_TIMEOUT_SECONDS", "120"))
        self.vision_cloud_timeout_seconds = float(os.getenv("VISION_CLOUD_TIMEOUT_SECONDS", "180"))
        self.vision_cloud_stage_timeout_seconds = float(os.getenv("VISION_CLOUD_STAGE_TIMEOUT_SECONDS", "300"))
        self.vision_verification_timeout_seconds = float(os.getenv("VISION_VERIFICATION_TIMEOUT_SECONDS", "180"))
        self.vision_stage_timeout_seconds: float = float(os.getenv("VISION_STAGE_TIMEOUT_SECONDS", "600"))
        self.extraction_stage_timeout_seconds: float = float(
            os.getenv("EXTRACTION_STAGE_TIMEOUT_SECONDS", "1800")
        )
        self.source_job_timeout_seconds = float(os.getenv("SOURCE_JOB_TIMEOUT_SECONDS", "2400"))
        self.frontend_job_poll_timeout_seconds = float(os.getenv("FRONTEND_JOB_POLL_TIMEOUT_SECONDS", "3600"))
        self.vision_cache_enabled = os.getenv("VISION_CACHE_ENABLED", "true").lower() in {"1", "true", "yes"}
        self.vision_cache_ttl_seconds = float(os.getenv("VISION_CACHE_TTL_SECONDS", "3600"))
        self.vision_max_retries: int = int(os.getenv("VISION_MAX_RETRIES", "1"))
        self.vision_rate_limit_fallback: bool = False
        self.pipeline_config_version: str = os.getenv("PIPELINE_CONFIG_VERSION", "v1").strip()
        self.openrouter_api_key: str = ""

        # --- Database & Persistence Architecture (Supabase / Local) ---
        self.database_provider: str = os.getenv("DATABASE_PROVIDER", "file").strip().lower()
        # Supabase remains the authentication/legacy provider. This switch controls
        # canonical writes for NEW sources and their dependent learning records.
        self.source_persistence_provider = os.getenv("SOURCE_PERSISTENCE_PROVIDER", "supabase").strip().lower()
        if self.source_persistence_provider not in {"supabase", "postgres"}:
            raise ValueError("SOURCE_PERSISTENCE_PROVIDER must be supabase or postgres")
        # Independent of Supabase Auth/canonical source persistence; never auto-fallback.
        self.lesson_persistence_provider = os.getenv("LESSON_PERSISTENCE_PROVIDER", "file").strip().lower()
        self.postgres_dsn = SecretStr(os.getenv("POSTGRES_DSN", "").strip())
        self.postgres_pool_size = int(os.getenv("POSTGRES_POOL_SIZE", "4"))
        self.postgres_timeout_seconds = float(os.getenv("POSTGRES_TIMEOUT_SECONDS", "10"))
        if self.lesson_persistence_provider not in {"file", "postgres"}:
            raise ValueError("LESSON_PERSISTENCE_PROVIDER must be file or postgres")
        if not 1 <= self.postgres_pool_size <= 32:
            raise ValueError("POSTGRES_POOL_SIZE must be between 1 and 32")
        if not 0 < self.postgres_timeout_seconds <= 60:
            raise ValueError("POSTGRES_TIMEOUT_SECONDS must be between 0 and 60")
        if self.lesson_persistence_provider == "postgres" and not self.postgres_dsn.get_secret_value():
            raise ValueError("POSTGRES_DSN is required for PostgreSQL lesson persistence")
        if self.source_persistence_provider == "postgres" and (self.database_provider != "supabase" or self.lesson_persistence_provider != "postgres"):
            raise ValueError("PostgreSQL sources require Supabase authentication mode and PostgreSQL lesson persistence")
        self.supabase_auth_redirect_url: str = os.getenv("SUPABASE_AUTH_REDIRECT_URL", "").strip()
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "").strip()
        self.supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        self.supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "").strip()
        self.supabase_jwt_audience: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip()
        self.supabase_timeout_seconds: float = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "10"))
        import math
        for name in ("cloudflare_connect_timeout", "cloudflare_read_timeout", "cloudflare_write_timeout",
                     "cloudflare_overall_timeout", "vision_timeout_seconds", "vision_cloud_timeout_seconds",
                     "vision_cloud_stage_timeout_seconds", "vision_verification_timeout_seconds", "vision_stage_timeout_seconds",
                     "extraction_stage_timeout_seconds", "source_job_timeout_seconds", "frontend_job_poll_timeout_seconds", "vision_cache_ttl_seconds"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a finite positive number")
        if self.vision_max_retries not in (0, 1) or self.cloudflare_max_retries not in (0, 1):
            raise ValueError("Cloud and vision retries must be 0 or 1")
        if not 1 <= self.cloudflare_max_concurrency <= 32:
            raise ValueError("CLOUDFLARE_MAX_CONCURRENCY must be between 1 and 32")
        if self.cloudflare_vision_general_model != "@cf/google/gemma-4-26b-a4b-it" or self.cloudflare_vision_deep_model != "@cf/qwen/qwen3.8-27b":
            raise ValueError("Cloud visual tiers must use the two distinct qualified vision models")

    # ---------- Validation helpers ----------
    def is_allowed(self, filename: str) -> bool:
        ext = Path(filename).suffix.lstrip(".").lower()
        return ext in self.allowed_extensions

    def validate_runtime_configuration(self) -> dict[str, Any]:
        """Validate required runtime configuration without leaking secret values."""
        status: dict[str, Any] = {
            "llm_provider": self.llm_provider,
            "embedding_model": self.embedding_model,
            "requested_collection": self.requested_collection_name,
            "active_collection": self.collection_name,
            "qdrant_url": self.qdrant_url,
            "database_provider": self.database_provider,
            "supabase_connected": bool(self.supabase_url and (self.supabase_publishable_key or self.supabase_anon_key)),
            "warnings": [],
        }
        if self.database_provider == "supabase" and not status["supabase_connected"]:
            status["warnings"].append(
                "DATABASE_PROVIDER is set to 'supabase', but SUPABASE_URL or keys are not configured. "
                "Configure runtime credentials before enabling remote capabilities."
            )
        status.update(reasoning_provider=self.reasoning_provider, vision_provider=self.vision_provider,
            cloud_vision_general_model=self.cloudflare_vision_general_model, cloud_vision_deep_model=self.cloudflare_vision_deep_model,
            visual_independent_verifier=self.visual_independent_verifier,
            text_request_timeout=self.cloudflare_read_timeout, text_stage_timeout=self.cloudflare_overall_timeout,
            vision_request_timeout=self.vision_cloud_timeout_seconds, vision_cloud_stage_timeout=self.vision_cloud_stage_timeout_seconds,
            vision_stage_timeout=self.vision_stage_timeout_seconds, verification_timeout=self.vision_verification_timeout_seconds,
            extraction_timeout=self.extraction_stage_timeout_seconds, source_job_timeout=self.source_job_timeout_seconds,
            cloud_concurrency=self.cloudflare_max_concurrency,
            text_local_fallback=self.reasoning_local_fallback_enabled, vision_local_fallback=self.vision_local_fallback_enabled)
        if "cloudflare" in {self.reasoning_provider, self.vision_provider, self.visual_independent_verifier}:
            if not self.cloudflare_worker_url or not self.cloudflare_worker_secret.get_secret_value():
                status["warnings"].append("Cloudflare primary configuration is missing: set CLOUDFLARE_WORKER_URL and CLOUDFLARE_WORKER_SECRET. Requests fail explicitly; missing credentials do not enable local fallback.")
        return status


settings = Settings()
