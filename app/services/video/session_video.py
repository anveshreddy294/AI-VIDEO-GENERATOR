"""Canonical remediation adapter for the existing renderer; no file metadata fallback."""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
from uuid import UUID
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError
from ...core.config import settings
from ...core.supabase import SupabaseError, SupabaseConflict
from ..repositories.knowledge_repository import KnowledgeRepository, KnowledgeError
from ..mastery.session_learning import SessionLearningService
from ..assessment.schemas import VideoTarget
from ..retrieval import RetrievalRequest, RetrievalService
from .scene_schema import VideoArtifact, VideoPlan, ScenePlan, NarrationSegment, VideoJobStatus
from .scene_validator import validate_video_plan
from .video_compositor import validate_video_artifact

MAX_VIDEO_EXCERPTS = 6
MAX_EXCERPT_CHARACTERS = 360
MIN_SCENE_SECONDS = 8
NARRATION_WORDS_PER_SECOND = 2.5
VIDEO_DEADLINE_SECONDS = 300


class SessionVideoStatus(BaseModel):
    """Browser contract deliberately excludes paths, plans and provider diagnostics."""
    model_config = ConfigDict(extra="forbid")
    job_id: str
    status: VideoJobStatus
    stage: str
    progress: int
    duration_seconds: float
    error_code: str | None = None


class SessionVideo:
    def __init__(self, context: KnowledgeRepository, sid: UUID, remediation_id: str) -> None:
        self.context, self.sid, self.remediation_id = context, sid, remediation_id

    def transact(self, action: str, payload: dict[str, JsonValue] | None = None) -> dict[str, JsonValue] | None:
        try:
            result = self.context.runtime.admin_request("POST", "/rest/v1/rpc/visualai_remediation_video", body={
                "p_user_id": str(self.context.user.user_id), "p_learning_session_id": str(self.sid),
                "p_remediation_id": self.remediation_id, "p_action": action, "p_payload": payload or {},
            })
        except SupabaseConflict:
            raise KnowledgeError("CONFLICT") from None
        except SupabaseError:
            raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
        if result is None:
            return None
        if not isinstance(result, dict) or not isinstance(result.get("video"), dict):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        video = result["video"]
        metadata = video.get("output_metadata")
        if video.get("user_id") != str(self.context.user.user_id) or not isinstance(metadata, dict) or (
            metadata.get("learning_session_id") != str(self.sid)
            or metadata.get("remediation_job_id") != self.remediation_id
        ):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return result

    def get(self) -> dict[str, JsonValue]:
        result = self.transact("get")
        if result is None:
            raise KnowledgeError("NOT_FOUND")
        video = result["video"]
        assert isinstance(video, dict)
        return video

    @staticmethod
    def view(video: dict[str, JsonValue]) -> SessionVideoStatus:
        try:
            return SessionVideoStatus.model_validate({
                **{key: video[key] for key in ("job_id", "status", "stage", "progress", "duration_seconds")},
                "error_code": "VIDEO_RENDER_FAILED" if video["status"] == "FAILED" else None,
            })
        except (KeyError, ValidationError):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None

    def prepare(self) -> tuple[SessionVideoStatus, VideoTarget | None]:
        service = SessionLearningService(self.context)
        learning = service._learning(self.sid, active=True)
        saved = service.repository.transact(learning, "load")
        job = next((j for j in saved.remediation if j.job_id == self.remediation_id), None)
        if job is None:
            raise KnowledgeError("NOT_FOUND")
        existing = self.transact("get")
        if existing is not None:
            video = existing["video"]
            assert isinstance(video, dict)
            return self.status(video), None
        record = next((r for r in saved.mastery if r.concept_id == job.concept_id), None)
        if record is None or record.mastery_state != "REMEDIATING" or record.remediation_attempt_count != job.attempt_number or job.metadata.get("completed"):
            raise KnowledgeError("CONFLICT")
        bundle = RetrievalService().retrieve(self.context, RetrievalRequest(
            source_id=learning.source_id, source_version=learning.source_version,
            topic_id=learning.topic_id, subtopic_id=learning.subtopic_id, concept_ids=[job.concept_id],
            query="Review selected canonical evidence", purpose="remediation", retrieval_mode="exact",
            include_prerequisites=False, max_items=MAX_VIDEO_EXCERPTS,
        ))
        if bundle.outcome != "READY" or not bundle.items or bundle.scope.user_id != learning.user_id or any(
            i.source_id != learning.source_id or i.source_version != learning.source_version
            or job.concept_id not in i.concept_ids for i in bundle.items
        ):
            raise KnowledgeError("NOT_READY")
        concept = self.context.get_concept(bundle.scope, job.concept_id)
        if concept is None:
            raise KnowledgeError("NOT_FOUND")
        excerpts = list(dict.fromkeys(i.excerpt.strip() for i in bundle.items if i.excerpt.strip()))
        # Quote-only slides retain literal evidence; no model inference or unsupported explanation.
        parts = [quote[start:start+MAX_EXCERPT_CHARACTERS] for quote in excerpts
                 for start in range(0, len(quote), MAX_EXCERPT_CHARACTERS)]
        if not parts or len(parts)>MAX_VIDEO_EXCERPTS:
            raise KnowledgeError("PAYLOAD_TOO_LARGE")
        chunks = [i.chunk_id for i in bundle.items]
        content = sorted({i.content_id for i in bundle.items})
        durations = [max(MIN_SCENE_SECONDS, math.ceil(len(quote.split()) / NARRATION_WORDS_PER_SECOND)) for quote in parts]
        target = VideoTarget(student_id=str(learning.user_id), session_id=str(self.sid),
            source_id=learning.source_id, concept_id=job.concept_id, concept_name=concept.name,
            target_seconds=sum(durations), chunk_ids=chunks, source_content_ids=content)
        plan = VideoPlan(student_id=target.student_id, source_id=target.source_id,
            concept_id=target.concept_id, concept_name=target.concept_name,
            duration_seconds=target.target_seconds, source_chunk_ids=chunks, source_content_ids=content,
            scenes=[ScenePlan(scene_index=n, title=concept.name, text=quote, narration=quote,
                duration_seconds=durations[n], source_chunk_ids=chunks) for n,quote in enumerate(parts)],
            narration=[NarrationSegment(scene_index=n,text=quote,target_seconds=durations[n]) for n,quote in enumerate(parts)])
        validate_video_plan(plan)
        claimed = self.transact("claim", {"plan": plan.model_dump(mode="json")})
        if claimed is None:
            raise KnowledgeError("NOT_FOUND")
        video = claimed["video"]
        assert isinstance(video, dict)
        return self.view(video), target if claimed.get("claimed") is True else None

    def plan(self, target: VideoTarget) -> VideoPlan:
        video = self.get()
        try:
            plan = VideoPlan.model_validate(video.get("plan"))
        except ValidationError:
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
        if (plan.student_id,plan.source_id,plan.concept_id) != (str(self.context.user.user_id),target.source_id,target.concept_id):
            raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
        return plan

    def save(self, artifact: VideoArtifact) -> None:
        self.transact("save", artifact.model_dump(mode="json"))

    def status(self, video: dict[str, JsonValue] | None = None) -> SessionVideoStatus:
        """Report actual validated media duration without rewriting terminal rows."""
        owned = self.get() if video is None else video
        result = self.view(owned)
        if result.status == VideoJobStatus.COMPLETED:
            try:
                metadata = validate_video_artifact(self._media_path(owned), expect_audio=True)
                duration = float(metadata["duration"])
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                raise KnowledgeError("NOT_READY") from None
            if not math.isfinite(duration) or duration <= 0:
                raise KnowledgeError("NOT_READY")
            result.duration_seconds = duration
        return result

    def stream_path(self) -> Path:
        return self._media_path(self.get())

    @staticmethod
    def _media_path(video: dict[str, JsonValue]) -> Path:
        if video.get("status") != "COMPLETED":
            raise KnowledgeError("NOT_READY")
        raw = video.get("video_path")
        if not isinstance(raw,str):
            raise KnowledgeError("NOT_READY")
        path = Path(raw).resolve()
        if not path.is_relative_to(settings.renders_dir.resolve()) or path.suffix.lower() != ".mp4" or not path.is_file():
            raise KnowledgeError("NOT_READY")
        return path


async def render_session_video(adapter: SessionVideo, target: VideoTarget, job_id: str) -> None:
    """Bound a render; deadline failures remain durable and do not consume a new learning attempt."""
    from .engine import execute_video_generation_job
    try:
        async with asyncio.timeout(VIDEO_DEADLINE_SECONDS):
            await execute_video_generation_job(target, job_id=job_id, canonical=adapter, mock_tts=False)
    except TimeoutError:
        adapter.save(VideoArtifact(job_id=job_id,student_id=str(adapter.context.user.user_id),
            source_id=target.source_id,concept_id=target.concept_id,concept_name=target.concept_name,
            status=VideoJobStatus.FAILED,stage="FAILED",error="VIDEO_RENDER_TIMEOUT"))
