"""Event-level timeline builder.

Given semantic plan events (with anchor_phrases) and WhisperX word
timestamps, produces a timed event timeline where each event has:
  - start: seconds from scene beginning
  - run_time: animation duration (weighted by event.importance)
  - hold_after: explicit wait after animation (for 'hold' events)

Synchronization rule:
  event.start = phrase_start + phase_offset
  where phase_offset = {before: -0.25s, on: 0.0s, after: phrase_duration}

run_time is allocated from event.importance (1-5):
  importance 1 → 0.40s
  importance 2 → 0.65s
  importance 3 → 0.95s
  importance 4 → 1.40s
  importance 5 → 2.00s

'hold' event type gets hold_after = phrase_duration (LLM-specified phrase
indicates how long to stay still), run_time = 0.0.
"""
from __future__ import annotations

import re
from typing import Any

IMPORTANCE_RT: dict[int, float] = {1: 0.40, 2: 0.65, 3: 0.95, 4: 1.40, 5: 2.00}
PHASE_OFFSET: dict[str, float] = {"before": -0.25, "on": 0.0, "after": 0.0}
_MIN_RT = 0.35
_TAIL_RESERVE = 0.50  # seconds reserved for final FadeOut


def build_event_timeline(
    events: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
    audio_duration: float,
) -> dict[str, Any]:
    """Build a timed event list from semantic events + word alignment.

    Returns:
        {
            "total": float,  # audio_duration
            "events": [{"id", "start", "run_time", "hold_after"}, ...]
        }
    """
    timed: list[dict[str, Any]] = []
    last_end = 0.0  # tracks sequential upper bound

    for ev in events:
        eid = ev["id"]
        phrase = ev.get("anchor_phrase", "").strip()
        phase = ev.get("phase", "on")
        importance = max(1, min(5, int(ev.get("importance", 3))))
        ev_type = ev.get("type", "")

        # Locate phrase in word timestamps
        span = _find_phrase_span(phrase, word_timestamps) if phrase and word_timestamps else None

        if span is not None:
            phrase_start, phrase_end = span
            phrase_dur = phrase_end - phrase_start
            offset = PHASE_OFFSET.get(phase, 0.0)
            if phase == "after":
                offset = phrase_dur
            start = max(phrase_start + offset, last_end)
        else:
            # Fallback: place event right after the previous one with a small gap
            start = last_end + 0.2

        # run_time
        if ev_type == "hold":
            # For 'hold', run_time is the phrase duration (the silence we want)
            hold_dur = (phrase_end - phrase_start) if span else (importance * 0.4)
            hold_dur = max(hold_dur, 0.6)
            run_time = 0.0
            hold_after = round(hold_dur, 3)
        else:
            run_time = max(IMPORTANCE_RT.get(importance, 0.95), _MIN_RT)
            hold_after = 0.0

        timed.append({
            "id": eid,
            "start": round(start, 3),
            "run_time": round(run_time, 3),
            "hold_after": round(hold_after, 3),
        })

        last_end = start + run_time + hold_after

    # Safety: ensure no event starts after audio_duration - tail_reserve
    usable = audio_duration - _TAIL_RESERVE
    timed = _clamp_to_usable(timed, usable)

    return {
        "total": round(audio_duration, 3),
        "events": timed,
    }


# ---------------------------------------------------------------------------
# Phrase span finder (keep from old timeline_builder, renamed)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _find_phrase_span(
    phrase: str, words: list[dict[str, Any]]
) -> tuple[float, float] | None:
    """Find the (start, end) time window for a phrase in the word stream.

    Tries exact token match first; falls back to first-word anchor.
    """
    phrase_tokens = _normalize(phrase).split()
    if not phrase_tokens or not words:
        return None

    word_tokens = [_normalize(w.get("word", "")) for w in words]
    n = len(phrase_tokens)

    # Exact window match
    for i in range(len(word_tokens) - n + 1):
        if word_tokens[i : i + n] == phrase_tokens:
            return float(words[i]["start"]), float(words[i + n - 1]["end"])

    # First-word anchor with best effort
    for i, wt in enumerate(word_tokens):
        if wt == phrase_tokens[0]:
            end_idx = min(i + n - 1, len(words) - 1)
            return float(words[i]["start"]), float(words[end_idx]["end"])

    return None


# ---------------------------------------------------------------------------
# Clamp events to usable duration
# ---------------------------------------------------------------------------


def _clamp_to_usable(
    timed: list[dict[str, Any]], usable: float
) -> list[dict[str, Any]]:
    """Shift any events that would exceed `usable` seconds back in time."""
    result = []
    running = 0.0
    for ev in timed:
        start = max(ev["start"], running)
        end = start + ev["run_time"] + ev["hold_after"]
        if end > usable:
            # Try to fit by clamping run_time
            available = max(usable - start, _MIN_RT)
            rt = min(ev["run_time"], available) if ev["run_time"] > 0 else 0.0
            ha = min(ev["hold_after"], max(usable - start - rt, 0.0))
            result.append({**ev, "start": round(start, 3), "run_time": round(rt, 3), "hold_after": round(ha, 3)})
            running = start + rt + ha
        else:
            result.append({**ev, "start": round(start, 3)})
            running = end
    return result
