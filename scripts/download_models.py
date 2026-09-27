#!/usr/bin/env python3
"""VisualAI — Model & Dependency Download and Verification Manager.

Verifies and downloads all required AI models, neural weights, and runtime tools:
1. Ollama LLM Reasoning Model: llama3.2:3b
2. Ollama Multimodal Vision Model: gemma3:4b
3. Ollama Vector Embedding Model: nomic-embed-text
4. Faster-Whisper Speech Recognition: base
5. System Dependencies: FFmpeg, Python packages
"""

import sys
import os
import json
import shutil
import argparse
import urllib.request
import urllib.error

REQUIRED_OLLAMA_MODELS = {
    "llama3.2:3b": {
        "role": "Assessment Generation & Knowledge Profiling Reasoning",
        "size_approx": "~2.0 GB",
        "recommended": True,
    },
    "gemma3:4b": {
        "role": "Multimodal Vision & Technical Diagram OCR Extraction",
        "size_approx": "~3.3 GB",
        "recommended": True,
    },
    "nomic-embed-text": {
        "role": "768-dimensional Semantic Chunk & Concept Embeddings",
        "size_approx": "~274 MB",
        "recommended": True,
    },
}

WHISPER_MODEL = "base"


def check_ffmpeg() -> bool:
    """Check if ffmpeg executable exists in PATH."""
    return shutil.which("ffmpeg") is not None


def get_ollama_host() -> str:
    """Get Ollama host URL from environment or default."""
    return os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def get_installed_ollama_models(host: str) -> list[str]:
    """Fetch list of models currently pulled in Ollama."""
    try:
        req = urllib.request.Request(f"{host}/api/tags", headers={"User-Agent": "VisualAI-ModelManager"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = [m.get("name", "").split(":")[0] + ":" + m.get("name", "").split(":")[-1] for m in data.get("models", [])]
            # Also add bare names
            bare_names = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            return list(set(models + bare_names))
    except Exception:
        return []


def is_ollama_running(host: str) -> bool:
    """Ping Ollama server."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def pull_ollama_model(host: str, model_name: str) -> bool:
    """Pull an Ollama model streaming progress to console."""
    print(f"\n[DOWNLOAD] Pulling Ollama model '{model_name}'...")
    url = f"{host}/api/pull"
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                print(f"[OK] Successfully downloaded '{model_name}'.")
                return True
            print(f"[OK] Model pull status: {data.get('status')}")
            return True
    except Exception as exc:
        print(f"[ERROR] Failed to pull '{model_name}': {exc}")
        return False


def verify_whisper() -> bool:
    """Verify faster-whisper neural model download/cache."""
    try:
        from faster_whisper import WhisperModel
        print(f"[VERIFY] Loading Faster-Whisper '{WHISPER_MODEL}'...")
        _ = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print(f"[OK] Faster-Whisper '{WHISPER_MODEL}' model cached and ready.")
        return True
    except Exception as exc:
        print(f"[WARN] Faster-Whisper check deferred or failed: {exc}")
        return False


def inspect_all(host: str):
    """Print complete system readiness, installed models, and missing prerequisites."""
    print("\n========================================================")
    print("      VisualAI — Prerequisites & Model Status")
    print("========================================================\n")

    # 1. System executables
    print("[1] System Dependencies:")
    py_ver = sys.version.split()[0]
    print(f"  • Python:           {py_ver} ({'[OK]' if sys.version_info >= (3, 10) else '[WARN: Python 3.10+ recommended]'})")
    ffmpeg_ok = check_ffmpeg()
    print(f"  • FFmpeg:           {'[OK] Found in PATH' if ffmpeg_ok else '[MISSING] Run: brew install ffmpeg (macOS) | sudo apt install ffmpeg (Linux)'}")

    # 2. Ollama Service
    print("\n[2] Ollama Service:")
    ollama_ok = is_ollama_running(host)
    print(f"  • Ollama Server:    {'[OK] Active on ' + host if ollama_ok else '[OFFLINE] Not reachable at ' + host + ' (run `ollama serve`)'}")

    # 3. Model Inventory
    print("\n[3] Required AI Models & Weights:")
    installed = get_installed_ollama_models(host) if ollama_ok else []
    all_models_ready = True

    for name, info in REQUIRED_OLLAMA_MODELS.items():
        base_name = name.split(":")[0]
        is_ready = any(name in m or base_name == m for m in installed)
        status_tag = "[READY]" if is_ready else "[NOT DOWNLOADED]"
        if not is_ready:
            all_models_ready = False
        print(f"  • {name:<20} {status_tag:<18} ({info['size_approx']})")
        print(f"    Role: {info['role']}")

    print("\n[4] Audio Alignment:")
    print(f"  • faster-whisper ({WHISPER_MODEL}): Automatic download on first video transcription / alignment run.")

    print("\n========================================================")
    if ffmpeg_ok and ollama_ok and all_models_ready:
        print("  STATUS: ALL REQUIRED MODELS & PREREQUISITES ARE READY!")
    else:
        print("  STATUS: SOME COMPONENTS REQUIRE DOWNLOAD OR STARTUP.")
        print("  Run with `--download` to pull all missing models automatically:")
        print("    python3 scripts/download_models.py --download")
    print("========================================================\n")


def main():
    parser = argparse.ArgumentParser(description="VisualAI Model & System Dependency Manager")
    parser.add_argument("--inspect", action="store_true", help="Inspect all system dependencies and model readiness")
    parser.add_argument("--download", action="store_true", help="Download all required Ollama models and neural weights")
    args = parser.parse_args()

    host = get_ollama_host()

    if args.download:
        print("\nStarting automated download of VisualAI models...")
        if not is_ollama_running(host):
            print(f"[ERROR] Ollama is not running at {host}.")
            print("Please start Ollama in another terminal with: `ollama serve` and rerun.")
            sys.exit(1)

        installed = get_installed_ollama_models(host)
        for name in REQUIRED_OLLAMA_MODELS:
            base_name = name.split(":")[0]
            if any(name in m or base_name == m for m in installed):
                print(f"[OK] '{name}' already downloaded.")
            else:
                pull_ollama_model(host, name)

        verify_whisper()
        inspect_all(host)
    else:
        # Default action: inspect
        inspect_all(host)


if __name__ == "__main__":
    main()
