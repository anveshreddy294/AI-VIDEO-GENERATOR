# Topic2Manim

AI educational video generation pipeline. Enter a topic, get a synchronized narrated Manim video.

## Stack

- **Gemini** (`gemini-2.5-flash`) — scene planning, Manim repair
- **NVIDIA NIM** (`google/gemma-3-27b-it`, `deepseek-ai/deepseek-r1`) — visual skeleton + Manim code
- **Piper TTS** — narration audio
- **WhisperX** — word-level forced alignment
- **Manim** — animation rendering
- **FFmpeg** — video merge

## Critical Rule

**LLMs never generate timing.** Timing comes only from Piper audio duration + WhisperX word timestamps. The sync engine injects `run_time` values into Manim code after alignment.

## Quick Start

```bash
chmod +x setup.sh
./setup.sh
source .venv/bin/activate

# Add keys to .env
cp .env.example .env
# GEMINI_API_KEY=...
# NVIDIA_API_KEY=...

python main.py "Explain Newton's First Law"
```

Output: `data/renders/final_video.mp4`

## Pipeline

```
Topic → Gemini (Scene JSON)
      → Narration + Visual Skeleton (no timing)
      → Piper TTS → WAV
      → WhisperX → word timestamps
      → Sync Engine → timeline JSON
      → Manim Compiler (injects run_time)
      → Manim Render (retry via Gemini on failure)
      → FFmpeg merge → final_video.mp4
```

## Project Structure

```
main.py
modules/
  llm/          gemini_client, nvidia_client
  planning/     scene_json, narration, visual_skeleton
  tts/          piper_tts
  sync/         whisper_align, timeline_builder, sync_engine
  manim/        compiler, renderer
  video/        ffmpeg_merge
data/
  json/         scene plans + visual skeletons
  audio/        narration WAV files
  timelines/    synchronized timelines
  manim/        generated Python scripts
  renders/      final_video.mp4
samples/        example JSON artifacts
legacy/         original Flask-based codebase
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `NVIDIA_API_KEY` | — | NVIDIA NIM API key |
| `PIPER_MODEL` | `en_US-lessac-medium` | Piper voice model |
| `WHISPERX_MODEL` | `base` | WhisperX model size |
| `WHISPERX_DEVICE` | `cpu` | `cpu` or `cuda` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Fallbacks

- **Piper unavailable** → pyttsx3 system TTS → silent WAV (estimated duration)
- **WhisperX unavailable** → uniform word-level timestamps from audio duration

## License

MIT
