"""Central configuration: paths, environment variables, and logging."""
from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

PATHS = {
    "root": ROOT,
    "json": ROOT / "data" / "json",
    "audio": ROOT / "data" / "audio",
    "timelines": ROOT / "data" / "timelines",
    "manim": ROOT / "data" / "manim",
    "renders": ROOT / "data" / "renders",
    "piper_models": ROOT / "data" / "models" / "piper",
    "samples": ROOT / "samples",
}

for _path in PATHS.values():
    if isinstance(_path, Path):
        _path.mkdir(parents=True, exist_ok=True)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PIPER_MODEL = os.getenv("PIPER_MODEL", "en_US-lessac-medium")
USE_WHISPERX = os.getenv("USE_WHISPERX", "false").lower() in ("1", "true", "yes")
WHISPERX_MODEL = os.getenv("WHISPERX_MODEL", "base")
WHISPERX_DEVICE = os.getenv("WHISPERX_DEVICE", "cpu")
WHISPERX_COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")
MANIM_REPAIR_TIMEOUT = int(os.getenv("MANIM_REPAIR_TIMEOUT", "30"))
MANIM_REPAIR_MAX_CALLS = int(os.getenv("MANIM_REPAIR_MAX_CALLS", "1"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

NVIDIA_PLANNER_MODEL = os.getenv("NVIDIA_PLANNER_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_REPAIR_MODEL = os.getenv("NVIDIA_REPAIR_MODEL", "deepseek-ai/deepseek-r1")

MANIM_QUALITY = os.getenv("MANIM_QUALITY", "-qm")
MANIM_MAX_RETRIES = int(os.getenv("MANIM_MAX_RETRIES", "3"))

FINAL_VIDEO = PATHS["renders"] / "final_video.mp4"


@dataclass
class RenderWorkspace:
    """Isolated per-request directory tree for all pipeline artifacts."""

    session_id: str
    root: Path
    manim_dir: Path
    media_dir: Path
    audio_dir: Path
    timelines_dir: Path
    tmp_dir: Path
    scenes_dir: Path

    @classmethod
    def make(cls, session_id: str) -> RenderWorkspace:
        root = PATHS["renders"] / session_id
        workspace = cls(
            session_id=session_id,
            root=root,
            manim_dir=root / "manim",
            media_dir=root / "manim" / "media",
            audio_dir=root / "audio",
            timelines_dir=root / "timelines",
            tmp_dir=root / "tmp",
            scenes_dir=root / "scenes",
        )
        workspace.reset()
        return workspace

    def reset(self) -> None:
        """Remove any prior artifacts for this session id and recreate dirs."""
        if self.root.exists():
            shutil.rmtree(self.root)
        for directory in (
            self.manim_dir,
            self.media_dir,
            self.audio_dir,
            self.timelines_dir,
            self.tmp_dir,
            self.scenes_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Return a configured module logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False
    return logger


def ensure_api_keys() -> None:
    """Validate that at least one LLM API key is present."""
    if not NVIDIA_API_KEY and not GEMINI_API_KEY:
        raise EnvironmentError(
            "No LLM API key found. Set NVIDIA_API_KEY (or GEMINI_API_KEY) in .env"
        )
