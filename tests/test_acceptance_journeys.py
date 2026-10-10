"""Acceptance verification for Journeys A, B, and C."""
import json
import time
import tempfile
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.sources import source_repository
from app.services.video.video_compositor import probe_media, validate_video_artifact
from app.services.educational_content import (
    EducationalContentService,
    get_educational_lesson,
)
from app.core.reasoning import ReasoningRequest, ReasoningResult, Telemetry
from tests.test_source_supabase import context, Context, OWNER, OTHER


class MockProvider:
    def __init__(self) -> None:
        self.requests: list[ReasoningRequest] = []

    def generate(self, request: ReasoningRequest) -> ReasoningResult:
        self.requests.append(request)
        if request.response_schema and request.response_schema.get("title") == "DescriptiveGrade":
            resp = json.dumps({"score_fraction": 0.9, "feedback": "Correct branching and comparison."})
        elif request.task == "notes":
            resp = json.dumps({
                "title": "Study Notes: Binary Search Trees",
                "summary": "A binary search tree maintains sorted keys for O(log n) lookups.",
                "key_points": ["Left child < parent", "Right child > parent"],
                "key_concepts": [{"name": "Inorder Traversal", "explanation": "Visits nodes in ascending order."}],
                "examples": ["Insert 5, then 3 (left), then 7 (right)."],
                "equations": ["h = O(log n)"],
                "provenance_kind": "AI_ENRICHED",
            })
        elif request.task == "flowchart":
            resp = json.dumps({
                "title": "Binary Search Tree Traversal",
                "nodes": [
                    {"id": "n1", "label": "Start at Root", "description": "Initialize traversal"},
                    {"id": "n2", "label": "Compare Key", "description": "Compare target with node key"},
                    {"id": "n3", "label": "Go Left", "description": "If target < key"},
                    {"id": "n4", "label": "Go Right", "description": "If target > key"},
                    {"id": "n5", "label": "Found Target", "description": "If target == key"},
                ],
                "edges": [
                    {"from_node": "n1", "to_node": "n2", "label": "Begin"},
                    {"from_node": "n2", "to_node": "n3", "label": "Smaller"},
                    {"from_node": "n2", "to_node": "n4", "label": "Greater"},
                    {"from_node": "n2", "to_node": "n5", "label": "Equal"},
                ],
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


def test_journey_a_topic_only_binary_search_trees(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    """JOURNEY A: Topic-only learning for Binary Search Trees."""
    remote, repo, _ = context
    provider = MockProvider()
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: provider)

    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo

        # 1. Topic-only creation
        resp = client.post('/educational-content', json={'topic': 'Binary Search Trees'})
        assert resp.status_code == 200, f"Creation failed: {resp.text}"
        lesson_data = resp.json()
        lesson_id = lesson_data['content_id']
        assert lesson_data['status'] == "READY"
        assert lesson_data['topic'] == "Binary Search Trees"
        assert len(lesson_data['key_concepts']) > 0
        assert len(lesson_data['explanation']) > 50

        # 2. Notes Generation
        n_resp = client.post(f'/educational-content/{lesson_id}/notes')
        assert n_resp.status_code == 200, f"Notes failed: {n_resp.text}"
        notes = n_resp.json()
        assert notes['summary']
        assert len(notes['key_points']) > 0

        # 3. Flowchart Diagram Generation
        d_resp = client.post(f'/educational-content/{lesson_id}/diagram')
        assert d_resp.status_code == 200, f"Diagram failed: {d_resp.text}"
        diagram = d_resp.json()
        assert len(diagram['nodes']) >= 2
        assert len(diagram['edges']) >= 1
        node_ids = {n.get('node_id', n.get('id')) for n in diagram['nodes']}
        for edge in diagram['edges']:
            assert edge['from_node'] in node_ids
            assert edge['to_node'] in node_ids

        # 4. Assessment Generation (MCQs + Descriptive)
        a_resp = client.post(f'/educational-content/{lesson_id}/assessment')
        assert a_resp.status_code == 200, f"Assessment failed: {a_resp.text}"
        assessment = a_resp.json()
        assert len(assessment['mcqs']) > 0
        assert assessment.get('descriptive') is not None
        # Ensure answer key is secure
        assert 'correct_index' not in assessment['mcqs'][0], "SECURITY: correct_index leaked"
        assert 'sample_answer' not in assessment['descriptive']

        # 5. Assessment Submission & Grading
        mcq_id = assessment['mcqs'][0]['question_id']
        sub_resp = client.post(
            f'/educational-content/{lesson_id}/assessment/submit',
            json={'mcq_answers': {mcq_id: 0}, 'descriptive_answers': {assessment['descriptive']['question_id']: 'Compare the target to the node key; go left if smaller and right if larger.'}}
        )
        assert sub_resp.status_code == 200, f"Grading failed: {sub_resp.text}"
        sub_res = sub_resp.json()
        assert 'score' in sub_res and 'percentage' in sub_res
        assert 'mcq_results' in sub_res

        # 6. Ask / RAG
        ask_resp = client.post(
            f'/educational-content/{lesson_id}/ask',
            json={'question': 'How does lookup work in a BST?'}
        )
        assert ask_resp.status_code == 200, f"Ask failed: {ask_resp.text}"
        assert len(ask_resp.json()['answer']) > 20

        # 7. Video Generation Pipeline
        v_resp = client.post(f'/educational-content/{lesson_id}/video')
        assert v_resp.status_code == 200, f"Video trigger failed: {v_resp.text}"

        # Poll status
        st = None
        for _ in range(60):
            time.sleep(1)
            status_resp = client.get(f'/educational-content/{lesson_id}/video/status')
            st = status_resp.json()
            if st.get('status') in ('COMPLETED', 'FAILED'):
                break

        assert st and st.get('status') in ('COMPLETED', 'completed'), f"Video render failed: {st}"

        # Stream MP4 and ffprobe check
        v_stream = client.get(f'/educational-content/{lesson_id}/video/stream')
        assert v_stream.status_code == 200
        assert len(v_stream.content) > 100000

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
            tf.write(v_stream.content)
            t_path = Path(tf.name)

        try:
            meta = validate_video_artifact(t_path, expect_audio=True)
            assert meta["video_codec"] is not None, "Video stream missing"
            assert meta["audio_codec"] is not None, "Audio narration stream missing"
            assert 18 <= meta["duration"] <= 40, f"Unexpected duration: {meta['duration']}s"
        finally:
            if t_path.exists():
                t_path.unlink()

        # 8. Durable persistence check
        persisted = get_educational_lesson(OWNER, UUID(lesson_id))
        assert persisted is not None
        assert persisted.teaching.topic == "Binary Search Trees"
        assert persisted.notes is not None
        assert persisted.diagram is not None
        assert persisted.assessment is not None
        assert persisted.video_status == "COMPLETED"


def test_journey_b_source_grounded_learning(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    """JOURNEY B: Uploaded-source learning with extraction observations."""
    remote, repo, path = context
    provider = MockProvider()
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: provider)
    from app.services.ingestion.source_ingestion import ingest_source

    # Ingest fixture source
    res = ingest_source(repo, path, "linear_models.txt")
    source_id = str(res["source_id"])

    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo

        # Create educational content from source
        resp = client.post('/educational-content', json={'source_id': source_id, 'source_version': 1})
        assert resp.status_code == 200, f"Source lesson failed: {resp.text}"
        data = resp.json()
        lesson_id = data['content_id']
        assert data['status'] == "READY"
        assert data['source_id'] == source_id

        # Check diagram
        d_resp = client.post(f'/educational-content/{lesson_id}/diagram')
        assert d_resp.status_code == 200
        assert len(d_resp.json()['nodes']) >= 2

        # Check ask
        a_resp = client.post(f'/educational-content/{lesson_id}/ask', json={'question': 'Explain the concept'})
        assert a_resp.status_code == 200
        assert len(a_resp.json()['answer']) > 20


def test_journey_c_bounded_failures_and_isolation(context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    """JOURNEY C: Bounded failures, error handling and tenant isolation."""
    remote, repo, _ = context
    provider = MockProvider()
    monkeypatch.setattr("app.services.educational_content.get_reasoning_router", lambda: provider)

    with TestClient(app) as client:
        app.dependency_overrides[source_repository] = lambda: repo

        # 1. 404 on nonexistent lesson
        bad_resp = client.get('/educational-content/00000000-0000-0000-0000-000000000000')
        assert bad_resp.status_code == 404

        # 2. 404 for foreign owner on existing lesson
        create_resp = client.post('/educational-content', json={'topic': 'Algorithms'})
        assert create_resp.status_code == 200
        lesson_id = create_resp.json()['content_id']

        other_repo = repo.__class__(repo.user.__class__(OTHER, None, {}), 'other-token', repo.runtime)
        app.dependency_overrides[source_repository] = lambda: other_repo
        foreign_resp = client.get(f'/educational-content/{lesson_id}')
        assert foreign_resp.status_code == 404
