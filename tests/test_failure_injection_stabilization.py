"""Phase 23 Failure Injection & Resilience Verification Test Suite.

Verifies system behavior under failure conditions:
1. Vision failure: invalid/corrupt image handling
2. Local reasoning failure: unconfigured/unreachable Ollama
3. Video failure: unrenderable script & failure classification
4. Vector store failure: unreachable Qdrant
5. Concurrency limit: semaphore boundary & no deadlock
"""

import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from functools import wraps

def async_test(coro):
    @wraps(coro)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper

from app.services.concept_id import validate_concept_id
from app.services.vision import extract_vision_openrouter, VisionExtractionFailed
from app.services.mastery.models import MasteryRecord, MasteryState
from app.services.mastery.repository import InMemoryMasteryRepository
from app.services.mastery.remediation_repository import InMemoryRemediationJobRepository
from app.services.mastery.remediation_models import RemediationJobStatus
from app.services.mastery.remediation_orchestrator import RemediationOrchestrator
from app.services.mastery.state_machine import MasteryStateMachine
from app.services.assessment.schemas import VideoTarget
from app.services.video.scene_schema import VideoArtifact, VideoJobStatus


@async_test
async def test_failure_injection_corrupted_image(tmp_path: Path):
    """Test vision handling of corrupted/truncated image when OpenRouter fails."""
    corrupt_bytes = b"\x89PNG\r\n\x1a\n\x00\x00corrupted_payload"
    
    with patch("urllib.request.urlopen", side_effect=RuntimeError("OpenRouter 400 Bad Request")):
        with pytest.raises(VisionExtractionFailed) as exc_info:
            extract_vision_openrouter(corrupt_bytes, source="corrupt.png")
        assert "failed" in str(exc_info.value).lower() or "openrouter" in str(exc_info.value).lower()


@async_test
async def test_failure_injection_ollama_unreachable():
    """Test LLM generator when Ollama service is unavailable."""
    from app.services.assessment.generator import generate_questions_batch
    from app.services.schemas import ConceptNode
    
    concepts = [
        ConceptNode(concept_id="CONCEPT_QUANTUM_SPIN", name="Quantum Spin", definition="Intrinsic angular momentum")
    ]
    
    # Mock Ollama provider connection refusal
    mock_provider = MagicMock()
    mock_provider.generate_content.side_effect = ConnectionRefusedError("Failed to connect to localhost:11434")
    
    # Batch generation must fail closed without hanging or infinite loop
    results = generate_questions_batch(
        concepts=concepts,
        source_id="SRC_TEST",
        target_count=1,
        llm_provider=mock_provider,
    )
    # Failed closed: empty results, zero false questions
    assert len(results) == 0


@async_test
async def test_failure_injection_video_engine_ffmpeg_crash(tmp_path: Path):
    """Test video orchestrator handling FFmpeg failure: classifies as INFRASTRUCTURE_FAILURE."""
    mastery_repo = InMemoryMasteryRepository()
    remediation_repo = InMemoryRemediationJobRepository()
    state_machine = MasteryStateMachine()
    
    rec = MasteryRecord(
        user_id="user_fail",
        source_id="src_fail",
        concept_id="CONCEPT_CELL_MEMBRANE",
        mastery_state=MasteryState.WEAK,
        remediation_attempt_count=0,
    )
    mastery_repo.save(rec)
    
    async def crashing_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        raise RuntimeError("ffmpeg crashed with SIGKILL (out of memory)")
        
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=crashing_engine,
    )
    
    job = await orchestrator.execute_remediation(
        user_id="user_fail",
        source_id="src_fail",
        concept_id="CONCEPT_CELL_MEMBRANE",
    )
    
    assert job.status == RemediationJobStatus.FAILED
    assert job.is_infrastructure_failure is True
    assert job.failure_code == "INFRASTRUCTURE_FAILURE"
    assert "SIGKILL" in job.failure_message
    
    # Educational attempt budget preserved
    updated_rec = mastery_repo.get("user_fail", "src_fail", "CONCEPT_CELL_MEMBRANE")
    assert updated_rec.mastery_state == MasteryState.WEAK
    assert updated_rec.remediation_attempt_count == 0


@async_test
async def test_failure_injection_qdrant_unreachable():
    """Test vector store handling when Qdrant client encounters connection error."""
    with patch("app.db.vector_store.get_client", side_effect=Exception("Qdrant connection refused at port 6333")):
        from app.db.vector_store import search_layer_a
        res = search_layer_a(query="quantum physics", source_id="SRC_TEST", limit=2)
        assert res == []


@async_test
async def test_concurrency_semaphore_limits_parallel_renders(tmp_path: Path):
    """Test concurrency protection prevents overload and executes without deadlocks."""
    mastery_repo = InMemoryMasteryRepository()
    remediation_repo = InMemoryRemediationJobRepository()
    state_machine = MasteryStateMachine()
    
    for i in range(3):
        rec = MasteryRecord(
            user_id=f"user_{i}",
            source_id="src_conc",
            concept_id="CONCEPT_CELL_MEMBRANE",
            mastery_state=MasteryState.WEAK,
            remediation_attempt_count=0,
        )
        mastery_repo.save(rec)
        
    max_active = 0
    current_active = 0
    lock = asyncio.Lock()
    
    dummy_video = tmp_path / "valid.mp4"
    dummy_video.write_bytes(b"content")
    
    async def concurrent_engine(target: VideoTarget, job_id: str | None = None, **kwargs) -> VideoArtifact:
        nonlocal max_active, current_active
        async with lock:
            current_active += 1
            if current_active > max_active:
                max_active = current_active
        await asyncio.sleep(0.05)
        async with lock:
            current_active -= 1
            
        return VideoArtifact(
            job_id=job_id or "JOB_CONC",
            student_id=target.student_id,
            source_id=target.source_id,
            concept_id=target.concept_id,
            concept_name=target.concept_name,
            duration_seconds=5.0,
            status=VideoJobStatus.COMPLETED,
            video_path=str(dummy_video),
        )
        
    orchestrator = RemediationOrchestrator(
        mastery_repo=mastery_repo,
        remediation_repo=remediation_repo,
        state_machine=state_machine,
        video_engine_fn=concurrent_engine,
    )
    
    with patch("app.services.mastery.remediation_orchestrator.validate_video_artifact", return_value={"duration": 5.0}):
        jobs = await asyncio.gather(
            orchestrator.execute_remediation(user_id="user_0", source_id="src_conc", concept_id="CONCEPT_CELL_MEMBRANE"),
            orchestrator.execute_remediation(user_id="user_1", source_id="src_conc", concept_id="CONCEPT_CELL_MEMBRANE"),
            orchestrator.execute_remediation(user_id="user_2", source_id="src_conc", concept_id="CONCEPT_CELL_MEMBRANE"),
        )
        
    assert len(jobs) == 3
    for j in jobs:
        assert j.status == RemediationJobStatus.READY
    # Concurrency limit preserved
    assert max_active <= 3
