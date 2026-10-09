"""Verification of durable lesson features: notes, diagram, assessment, video, ask."""
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.reasoning import ReasoningRequest, ReasoningResult, Telemetry
from app.main import app
from app.api.sources import source_repository
from app.services.educational_content import (
    AssessmentSubmission,
    ContentRequest,
    EducationalContentService,
    get_educational_lesson,
)
from tests.test_source_supabase import context, Context, OWNER


class MockProvider:
    def __init__(self) -> None:
        self.requests: list[ReasoningRequest] = []

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        self.requests.append(request)
        if request.task == "notes":
            resp = json.dumps({
                "title": "Study Notes: Binary Search Trees",
                "summary": "A binary search tree maintains sorted keys for O(log n) lookups.",
                "key_points": ["Left child < parent", "Right child > parent"],
                "key_concepts": [{"name": "Inorder Traversal", "explanation": "Visits nodes in ascending order."}],
                "examples": ["Insert 5, then 3 (left), then 7 (right)."],
                "equations": ["h = O(log n)"],
                "provenance_kind": "AI_ENRICHED",
            })
        elif request.task == "assessment_structured":
            resp = json.dumps({
                "assessment_id": "assess_test",
                "lesson_id": "test",
                "mcqs": [
                    {
                        "question_id": "q1",
                        "prompt": "What is the lookup complexity in a balanced BST?",
                        "options": ["O(log n)", "O(n^2)", "O(1)", "O(n!)"],
                        "correct_index": 0,
                        "explanation": "Balanced trees halve the search space at each level.",
                    }
                ],
                "descriptive": {
                    "question_id": "d1",
                    "prompt": "Explain BST search logic.",
                    "sample_answer": "Compare target with node key; go left if smaller, right if larger.",
                    "grading_rubric": "Mentions comparison and branching.",
                },
                "created_at": "2026-10-09T00:00:00Z",
            })
        elif request.task == "qa":
            resp = "In a BST, search starts at root and compares target to node key."
        else:
            resp = json.dumps({
                "topic": "Binary Search Trees",
                "explanation": "A binary tree where each node key is greater than left keys and less than right keys.",
                "key_concepts": [
                    {"name": "Binary Search Property", "explanation": "Left < Node < Right"},
                    {"name": "Balanced BST", "explanation": "Height is logarithmic in number of nodes"}
                ],
                "examples": ["Searching for 15 in a tree rooted at 10 goes to the right subtree."],
                "equations": ["h = floor(log2(n))"],
                "relationships": [{"subject": "Left Subtree", "relation": "is smaller than", "object": "Root"}]
            })
        return ReasoningResult(
            response=resp,
            telemetry=Telemetry(provider="ollama", task=request.task, outcome="SUCCESS", model="test", transport_latency_seconds=0.1)
        )


def test_lesson_full_lifecycle(context: Context) -> None:
    remote, repo, _ = context
    provider = MockProvider()
    service = EducationalContentService(repo, provider)

    # 1. Create content & lesson
    content = service.generate(ContentRequest(topic="Binary Search Trees"))
    lesson_id = str(content.content_id)
    lesson = service.get_lesson(lesson_id)
    assert lesson is not None
    assert lesson.topic == "Binary Search Trees"
    assert lesson.user_id == OWNER

    # 2. Generate notes
    notes = service.generate_notes(lesson)
    assert notes.title == "Study Notes: Binary Search Trees"
    assert len(notes.key_points) > 0
    assert lesson.notes is not None

    # 3. Generate flowchart diagram
    diagram = service.generate_diagram(lesson)
    assert diagram.type == "FLOWCHART"
    assert len(diagram.nodes) >= 2
    assert len(diagram.edges) >= 1
    # Check structure validity
    node_ids = {n.node_id for n in diagram.nodes}
    for e in diagram.edges:
        assert e.from_node in node_ids
        assert e.to_node in node_ids

    # 4. Generate assessment
    assessment = service.generate_assessment(lesson)
    assert len(assessment.mcqs) == 1
    assert assessment.mcqs[0].correct_index == 0
    assert len(assessment.mcqs[0].options) == 4

    # 5. Grade submission
    sub_res = service.grade_assessment(lesson, AssessmentSubmission(
        mcq_answers={"q1": 0},
        descriptive_answer="Compare target with node key; go left if smaller and right if larger."
    ))
    assert sub_res.score >= 80.0
    assert sub_res.mcq_results[0]["is_correct"] is True
    assert len(lesson.submissions) == 1

    # 6. Ask question
    ask_res = service.ask(lesson, "How do lookups work?")
    assert "BST" in ask_res.answer or "search" in ask_res.answer
    assert len(lesson.ask_history) == 1

    # 7. Video plan creation
    plan = service.create_video_plan(content)
    assert plan.concept_name == "Binary Search Trees"
    assert 20 <= plan.duration_seconds <= 30
    assert len(plan.scenes) == 4
    assert len(plan.narration) == 4


def test_educational_endpoints_via_testclient(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote, repo, _ = context
    provider = MockProvider()
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: provider)

    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo

        # Create lesson
        resp = client.post("/educational-content", json={"topic": "Binary Search Trees"})
        assert resp.status_code == 200
        lesson_id = resp.json()["content_id"]

        # List lessons
        list_resp = client.get("/educational-content")
        assert list_resp.status_code == 200
        assert any(l["lesson_id"] == lesson_id for l in list_resp.json()["lessons"])

        # Notes
        notes_resp = client.post(f"/educational-content/{lesson_id}/notes")
        assert notes_resp.status_code == 200
        assert "summary" in notes_resp.json()

        # Diagram
        diag_resp = client.post(f"/educational-content/{lesson_id}/diagram")
        assert diag_resp.status_code == 200
        assert diag_resp.json()["type"] == "FLOWCHART"
        assert len(diag_resp.json()["nodes"]) > 0

        # Assessment (Public view should NOT expose correct_index or explanation)
        assess_resp = client.post(f"/educational-content/{lesson_id}/assessment")
        assert assess_resp.status_code == 200
        q = assess_resp.json()["mcqs"][0]
        assert "correct_index" not in q
        assert "explanation" not in q
        assert len(q["options"]) == 4

        # Submit Assessment
        submit_resp = client.post(f"/educational-content/{lesson_id}/assessment/submit", json={
            "mcq_answers": {"q1": 0},
            "descriptive_answer": "Binary Search Tree properties ensure left is smaller and right is larger."
        })
        assert submit_resp.status_code == 200
        assert "score" in submit_resp.json()
        assert submit_resp.json()["score"] > 0

        # Ask
        ask_resp = client.post(f"/educational-content/{lesson_id}/ask", json={"question": "What is the tree height?"})
        assert ask_resp.status_code == 200
        assert len(ask_resp.json()["answer"]) > 0

        # Detail endpoint
        detail_resp = client.get(f"/educational-content/{lesson_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["notes"] is not None
        assert detail_resp.json()["diagram"] is not None
        assert detail_resp.json()["assessment"] is not None
        assert len(detail_resp.json()["submissions"]) == 1


def test_video_generation_pipeline(context: Context) -> None:
    import asyncio
    from pathlib import Path
    remote, repo, _ = context
    provider = MockProvider()
    service = EducationalContentService(repo, provider)
    content = service.generate(ContentRequest(topic="Binary Search Trees"))
    lesson = service.get_lesson(str(content.content_id))
    assert lesson is not None

    plan = service.create_video_plan(content)
    job_id = f"JOB_TEST_{uuid4().hex[:6]}"
    lesson.video = {
        "job_id": job_id, "status": "QUEUED", "stage": "QUEUED",
        "progress": 5, "duration_seconds": float(plan.duration_seconds),
        "video_url": None, "error_code": None
    }
    from app.services.educational_content import save_educational_lesson
    save_educational_lesson(lesson)

    asyncio.run(service._render_video_pipeline(lesson.lesson_id, lesson.user_id, plan, job_id))

    updated = service.get_lesson(lesson.lesson_id)
    assert updated is not None and updated.video is not None
    assert updated.video["status"] == "COMPLETED"
    assert updated.video["progress"] == 100
    mp4_path = Path(updated.video["video_path"])
    assert mp4_path.exists()
    assert mp4_path.stat().st_size > 0
    # Probe with ffprobe
    from app.services.video.video_compositor import probe_media
    info = probe_media(mp4_path)
    streams = info.get("streams", [])
    assert any(s.get("codec_type") == "video" for s in streams)
    assert any(s.get("codec_type") == "audio" for s in streams)
    dur = float(info.get("format", {}).get("duration", 0))
    assert dur >= 20.0

