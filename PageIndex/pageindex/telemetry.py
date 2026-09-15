"""Pipeline telemetry collector."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StageMetrics:
    name: str
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    inference_calls: int = 0
    extractive_calls: int = 0
    title_only_calls: int = 0
    tokens_sent: int = 0
    tokens_truncated: int = 0
    batch_shrinks: int = 0
    timeouts: int = 0
    successes: int = 0
    failures: int = 0
    latencies_ms: List[float] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["avg_latency_ms"] = round(self.avg_latency_ms, 1)
        d.pop("started_at", None)
        d.pop("ended_at", None)
        return d


class PipelineMetrics:
    _stages: Dict[str, StageMetrics] = {}
    _pipeline_started_at: float = 0.0
    _meta: dict = {}

    @classmethod
    def reset(cls, *, pdf_name: str = "", mode: str = "cpu") -> None:
        cls._stages = {}
        cls._pipeline_started_at = time.time()
        cls._meta = {"pdf_name": pdf_name, "mode": mode}

    @classmethod
    def _stage(cls, name: str) -> StageMetrics:
        if name not in cls._stages:
            cls._stages[name] = StageMetrics(name=name)
        return cls._stages[name]

    @classmethod
    def stage_begin(cls, name: str) -> None:
        cls._stage(name).started_at = time.time()

    @classmethod
    def stage_end(cls, name: str) -> None:
        cls._stage(name).ended_at = time.time()

    @classmethod
    def record_inference(
        cls,
        stage: str,
        tokens: int,
        latency_ms: float,
        success: bool,
    ) -> None:
        s = cls._stage(stage)
        s.inference_calls += 1
        s.tokens_sent += tokens
        s.latencies_ms.append(latency_ms)
        if success:
            s.successes += 1
        else:
            s.failures += 1

    @classmethod
    def record_extractive(cls, stage: str) -> None:
        cls._stage(stage).extractive_calls += 1
        cls._stage(stage).successes += 1

    @classmethod
    def record_title_only(cls, stage: str) -> None:
        cls._stage(stage).title_only_calls += 1
        cls._stage(stage).successes += 1

    @classmethod
    def record_truncation(cls, stage: str, original: int, truncated_to: int) -> None:
        s = cls._stage(stage)
        s.tokens_truncated += max(0, original - truncated_to)

    @classmethod
    def record_shrink(cls, stage: str) -> None:
        cls._stage(stage).batch_shrinks += 1

    @classmethod
    def record_timeout(cls, stage: str) -> None:
        cls._stage(stage).timeouts += 1

    @classmethod
    def dump(cls, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **cls._meta,
            "total_runtime_s": round(time.time() - cls._pipeline_started_at, 2),
            "stages": {k: v.to_dict() for k, v in cls._stages.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
