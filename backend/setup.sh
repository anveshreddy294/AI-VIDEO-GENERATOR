#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Topic2Manim Setup ==="

# Detect architecture
ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  echo "Detected: Apple Silicon (arm64)"
elif [[ "$ARCH" == "x86_64" ]]; then
  echo "Detected: Intel (x86_64)"
else
  echo "Detected: $ARCH"
fi

# Homebrew dependencies
if command -v brew &>/dev/null; then
  echo "Installing system dependencies via Homebrew..."
  brew install ffmpeg basictex 2>/dev/null || true
  brew install pkg-config cmake 2>/dev/null || true
else
  echo "WARNING: Homebrew not found. Install ffmpeg and basictex manually."
fi

# LaTeX PATH
export PATH="/Library/TeX/texbin:$PATH"
if ! command -v latex &>/dev/null; then
  echo "WARNING: latex not found. Manim math rendering may fail."
  echo "  Add to ~/.zshrc: export PATH=\"/Library/TeX/texbin:\$PATH\""
fi

# Python virtual environment
if [[ ! -d ".venv" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# onnxruntime fix for Apple Silicon
if [[ "$ARCH" == "arm64" ]]; then
  pip install onnxruntime 2>/dev/null || pip install onnxruntime-silicon 2>/dev/null || true
fi

# Piper voice model
PIPER_DIR="data/models/piper"
PIPER_MODEL="${PIPER_MODEL:-en_US-lessac-medium}"
mkdir -p "$PIPER_DIR"

if [[ ! -f "$PIPER_DIR/${PIPER_MODEL}.onnx" ]]; then
  echo "Downloading Piper voice model: $PIPER_MODEL"
  BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
  curl -L -o "$PIPER_DIR/${PIPER_MODEL}.onnx" "${BASE_URL}/${PIPER_MODEL}.onnx" || true
  curl -L -o "$PIPER_DIR/${PIPER_MODEL}.onnx.json" "${BASE_URL}/${PIPER_MODEL}.onnx.json" || true
fi

# Data directories
mkdir -p data/json data/audio data/timelines data/manim data/renders data/models/piper samples

# .env setup
if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys."
fi

echo ""
echo "=== Setup Complete ==="
echo "Add GEMINI_API_KEY and NVIDIA_API_KEY to .env"
echo "Then run:"
echo "  source .venv/bin/activate"
echo "  python main.py \"Explain Newton's First Law\""
