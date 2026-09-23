"""Regression tests for audit findings (BLOCKER & HIGH).

Covers:
- BUG-AUDIT-01: FFmpeg Compositor Subprocess non-interactive Windows execution (stdin=DEVNULL, -nostdin).
- BUG-AUDIT-02: Qdrant search_source_chunks with session_id scoping.
- BUG-AUDIT-03: Assessment generator timeout respects config over hardcoded 8.0s.
"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.video.video_compositor import _run_subprocess_sync, composite_remedial_video


def test_bug_audit_01_subprocess_popen_uses_devnull_stdin():
    """Verify that _run_subprocess_sync explicitly binds stdin=subprocess.DEVNULL to prevent Windows console hangs."""
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        _run_subprocess_sync(["ffmpeg", "-version"], timeout=5.0, log_prefix="[test]")

        assert mock_popen.called
        _, kwargs = mock_popen.call_args
        assert kwargs.get("stdin") == subprocess.DEVNULL, "stdin must be set to subprocess.DEVNULL"


def test_bug_audit_01_composite_includes_nostdin_flag(tmp_path):
    """Verify that composite_remedial_video includes '-nostdin' in ffmpeg arguments."""
    import asyncio

    dummy_v = tmp_path / "v.mp4"
    dummy_a = tmp_path / "a.wav"
    dummy_out = tmp_path / "out.mp4"
    dummy_v.write_bytes(b"dummy_video_bytes")
    dummy_a.write_bytes(b"dummy_audio_bytes")

    with patch("app.services.video.video_compositor._resolve_binary", return_value="ffmpeg"), \
         patch("app.services.video.video_compositor.run_subprocess_bounded") as mock_run:
        
        # Simulate clean run
        dummy_out.write_bytes(b"final_mp4_bytes")
        mock_run.return_value = (0, b"", b"")
        with patch("app.services.video.video_compositor.validate_video_artifact", return_value={"duration": 10.0}):
            asyncio.run(composite_remedial_video(dummy_v, dummy_a, dummy_out))

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "-nostdin" in cmd, "FFmpeg command line must include '-nostdin' flag"


def test_bug_audit_02_session_scoping_and_isolation():
    """Verify that search_source_chunks preserves session isolation while allowing document chunks."""
    from app.db.vector_store import upsert_chunks, search_source_chunks
    from app.services.schemas import RichChunk

    src_a = "SRC_A_REGRESS_TEST"
    src_b = "SRC_B_REGRESS_TEST"

    # Chunk 1: Canonical document chunk (no session_id)
    doc_chunk = RichChunk(
        chunk_id="CHUNK_DOC_001",
        source_id=src_a,
        asset_id="AST_001",
        session_id=None,
        modality="txt",
        text="Newton's First Law describes the inertia of physical bodies at rest.",
    )

    # Chunk 2: Session Alpha chunk
    alpha_chunk = RichChunk(
        chunk_id="CHUNK_ALPHA_001",
        source_id=src_a,
        asset_id="AST_001",
        session_id="SESS_ALPHA",
        modality="txt",
        text="Interactive notes from student session Alpha about Newton's inertia.",
    )

    # Chunk 3: Session Beta chunk
    beta_chunk = RichChunk(
        chunk_id="CHUNK_BETA_001",
        source_id=src_a,
        asset_id="AST_001",
        session_id="SESS_BETA",
        modality="txt",
        text="Interactive notes from student session Beta about Newton's inertia.",
    )

    # Chunk 4: Source B chunk
    src_b_chunk = RichChunk(
        chunk_id="CHUNK_SRCB_001",
        source_id=src_b,
        asset_id="AST_002",
        session_id="SESS_ALPHA",
        modality="txt",
        text="Biological cellular respiration notes from session Alpha.",
    )

    upsert_chunks([doc_chunk, alpha_chunk, beta_chunk, src_b_chunk])

    # 1. Search with session_id="SESS_ALPHA" on source A
    hits_alpha = search_source_chunks(
        source_id=src_a,
        user_id="student_default",
        query="Newton inertia",
        session_id="SESS_ALPHA",
        score_threshold=0.01,
    )
    hit_ids_alpha = {h["chunk_id"] for h in hits_alpha}
    assert "CHUNK_DOC_001" in hit_ids_alpha, "Document chunk without session_id must be retrieved!"
    assert "CHUNK_ALPHA_001" in hit_ids_alpha, "Session Alpha chunk must be retrieved for Session Alpha!"
    assert "CHUNK_BETA_001" not in hit_ids_alpha, "Session Beta chunk must NEVER be retrieved for Session Alpha!"
    assert "CHUNK_SRCB_001" not in hit_ids_alpha, "Source B chunk must NEVER be retrieved for Source A!"

    # 2. Search with session_id="SESS_BETA" on source A
    hits_beta = search_source_chunks(
        source_id=src_a,
        user_id="student_default",
        query="Newton inertia",
        session_id="SESS_BETA",
        score_threshold=0.01,
    )
    hit_ids_beta = {h["chunk_id"] for h in hits_beta}
    assert "CHUNK_DOC_001" in hit_ids_beta, "Document chunk without session_id must be retrieved for Session Beta!"
    assert "CHUNK_BETA_001" in hit_ids_beta, "Session Beta chunk must be retrieved for Session Beta!"
    assert "CHUNK_ALPHA_001" not in hit_ids_beta, "Session Alpha chunk must NEVER be retrieved for Session Beta!"


def test_bug_audit_03_assessment_generator_timeout():
    """Verify that generate_question respects configured timeouts rather than hardcoding 8.0s."""
    from app.services.assessment.generator import generate_question
    from app.services.schemas import ConceptNode
    from app.core.llm import MockProvider

    concept = ConceptNode(
        concept_id="CONCEPT_TIMEOUT_TEST",
        name="Test Concept",
        definition="A concept definition for testing timeout propagation.",
        source_content_ids=["cu_1"],
    )

    mock_p = MockProvider()
    mock_p.timeout = 45.0
    recorded_timeout_during_call = None

    orig_generate = mock_p.generate_content
    def mock_gen(prompt):
        nonlocal recorded_timeout_during_call
        recorded_timeout_during_call = mock_p.timeout
        return orig_generate(prompt)

    mock_p.generate_content = mock_gen

    q = generate_question(
        concept=concept,
        source_id="SRC_TEST",
        provided_chunks=[{"chunk_id": "c1", "text": "Test concept definition in source text with sufficient length.", "page": 1, "content_ids": ["cu_1"]}],
        llm_provider=mock_p,
    )

    assert recorded_timeout_during_call is not None
    assert recorded_timeout_during_call != 8.0, f"Expected timeout != 8.0s, got {recorded_timeout_during_call}"
    assert recorded_timeout_during_call == 45.0, f"Expected timeout to be 45.0s, got {recorded_timeout_during_call}"
    assert mock_p.timeout == 45.0, "Expected provider timeout to be restored after generation"


