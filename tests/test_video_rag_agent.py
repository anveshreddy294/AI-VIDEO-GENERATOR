"""Comprehensive verification test suite for Interactive Video RAG & Timestamp Q&A Agent.

Verifies:
1. Timestamp-to-Scene Resolution: Accurate scene number and time window calculation.
2. Factual Retrieval & Grounding: Authoritative chunks and citations recovered.
3. Grounded QA Generation (Timestamped): Active scene context, citations, and suggestions.
4. General Question Handling: Concept-level Q&A when no playhead timestamp is provided.
5. REST API Integration: End-to-end POST /video/rag/ask endpoint with error handling.
"""

import json
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.main import app
from app.services.registry import save_content_units, save_knowledge_graph
from app.services.schemas import ConceptNode, ContentUnit, KnowledgeGraph
from app.services.video_gen.pipeline import VIDEOS_DIR
from app.services.video_gen.schemas import VideoScene, VideoScript
from app.services.video_rag.engine import (
    answer_video_question,
    get_active_scene_at_timestamp,
    load_video_script,
    retrieve_grounding_citations,
)
from app.services.video_rag.schemas import VideoQARequest, VideoQAResponse


class TestVideoRAGAgent(unittest.TestCase):
    def setUp(self):
        self.source_id = "SRC_rag_physics_01"
        self.concept_id = "CONCEPT_ENERGY"
        self.concept_name = "Conservation of Energy"
        self.video_id = "VID_test_rag_101"

        # 1. Seed KnowledgeGraph
        self.kg = KnowledgeGraph(
            concepts={
                self.concept_id: ConceptNode(
                    concept_id=self.concept_id,
                    name=self.concept_name,
                    definition="Energy cannot be created or destroyed, only transformed from one form to another.",
                    prerequisite_concept_ids=[],
                    source_content_ids=["CU_ENG_01", "CU_ENG_02"],
                )
            }
        )
        save_knowledge_graph(self.source_id, self.kg)

        # 2. Seed ContentUnits for grounding
        save_content_units(
            self.source_id,
            [
                ContentUnit(
                    content_id="CU_ENG_01",
                    source_id=self.source_id,
                    asset_id="AST_energy",
                    extraction_method="direct",
                    modality="txt",
                    text=(
                        "The total energy of an isolated system remains constant over time. "
                        "Kinetic energy can convert into potential energy, as observed in an oscillating pendulum."
                    ),
                    page_number=12,
                    token_count=35,
                ),
                ContentUnit(
                    content_id="CU_ENG_02",
                    source_id=self.source_id,
                    asset_id="AST_energy",
                    extraction_method="direct",
                    modality="txt",
                    text="Mechanical energy is the sum of potential energy and kinetic energy in an ideal system.",
                    page_number=13,
                    token_count=20,
                ),
            ],
        )

        # 3. Create mock VideoScript in workspace directory
        self.script = VideoScript(
            video_id=self.video_id,
            student_id="student_1",
            source_id=self.source_id,
            concept_id=self.concept_id,
            concept_name=self.concept_name,
            difficulty="intermediate",
            target_total_seconds=45,
            scenes=[
                VideoScene(
                    scene_number=1,
                    scene_type="title_hook",
                    title="Introduction to Energy Conservation",
                    narration="Why does a roller coaster speed up as it plunges downward?",
                    onscreen_bullets=["Energy transformations", "Total energy constancy"],
                    duration_seconds=10.0,
                ),
                VideoScene(
                    scene_number=2,
                    scene_type="concept_breakdown",
                    title="Kinetic and Potential Interplay",
                    narration="As potential energy drops, kinetic energy increases by the exact same amount.",
                    onscreen_bullets=["PE + KE = Constant", "Zero friction assumption"],
                    highlight_text="E_total = PE + KE",
                    duration_seconds=20.0,
                ),
                VideoScene(
                    scene_number=3,
                    scene_type="summary_takeaway",
                    title="Governing Rule",
                    narration="Remember, energy never disappears; it simply shifts form.",
                    onscreen_bullets=["Isolated system requirement", "Invariant total"],
                    duration_seconds=15.0,
                ),
            ],
            source_chunk_ids=["CU_ENG_01"],
        )

        # Write script.json to storage workspace
        workspace = VIDEOS_DIR / self.video_id
        workspace.mkdir(parents=True, exist_ok=True)
        script_file = workspace / "script.json"
        script_file.write_text(self.script.model_dump_json(indent=2), encoding="utf-8")

    def test_1_timestamp_to_scene_resolution(self):
        """Test 1: Verify accurate scene identification across timestamp boundaries."""
        # Timestamp 4.0s -> Scene 1 [0.0s - 10.0s]
        scene, start_s, end_s = get_active_scene_at_timestamp(self.script, 4.0)
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_number, 1)
        self.assertEqual(start_s, 0.0)
        self.assertEqual(end_s, 10.0)

        # Timestamp 15.0s -> Scene 2 [10.0s - 30.0s]
        scene, start_s, end_s = get_active_scene_at_timestamp(self.script, 15.0)
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_number, 2)
        self.assertEqual(start_s, 10.0)
        self.assertEqual(end_s, 30.0)

        # Timestamp 38.0s -> Scene 3 [30.0s - 45.0s]
        scene, start_s, end_s = get_active_scene_at_timestamp(self.script, 38.0)
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_number, 3)
        self.assertEqual(start_s, 30.0)
        self.assertEqual(end_s, 45.0)

        # Beyond duration (e.g. 60.0s) -> Clamped to Scene 3
        scene, start_s, end_s = get_active_scene_at_timestamp(self.script, 60.0)
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_number, 3)

    def test_2_factual_retrieval_and_citations(self):
        """Test 2: Verify authoritative ContentUnits / Qdrant citations are retrieved."""
        citations = retrieve_grounding_citations(
            source_id=self.source_id,
            concept_id=self.concept_id,
            query="What happens to kinetic energy?",
            limit=3,
        )
        self.assertGreaterEqual(len(citations), 1)
        self.assertTrue(any("kinetic" in c.text_preview.lower() or "energy" in c.text_preview.lower() for c in citations))
        self.assertIsNotNone(citations[0].chunk_id)

    def test_3_grounded_qa_generation_timestamped(self):
        """Test 3: Verify QA response includes active scene context, citations, and suggestions."""
        response = answer_video_question(
            video_id=self.video_id,
            question="Why does kinetic energy increase when potential energy drops?",
            timestamp=18.0,  # inside Scene 2
            mock_mode=True,
        )

        self.assertIsInstance(response, VideoQAResponse)
        self.assertEqual(response.video_id, self.video_id)
        self.assertEqual(response.concept_name, self.concept_name)

        # Active scene verification
        self.assertIsNotNone(response.active_scene)
        self.assertEqual(response.active_scene.scene_number, 2)
        self.assertEqual(response.active_scene.timestamp_label, "0:10 - 0:30")

        # Grounding & citations
        self.assertGreaterEqual(len(response.citations), 1)
        self.assertIn("Scene 2", response.answer)
        self.assertIn("Conservation of Energy", response.answer)

        # Follow-up suggestions
        self.assertGreaterEqual(len(response.suggested_questions), 2)

    def test_4_general_question_without_timestamp(self):
        """Test 4: Verify QA handles concept-level queries without active timestamp."""
        response = answer_video_question(
            video_id=self.video_id,
            question="What is the high-level takeaway of this lesson?",
            timestamp=None,
            mock_mode=True,
        )

        self.assertIsInstance(response, VideoQAResponse)
        self.assertIsNone(response.active_scene)
        self.assertIn("Conservation of Energy", response.answer)
        self.assertGreaterEqual(len(response.citations), 1)

    def test_5_rest_api_ask_endpoint(self):
        """Test 5: Verify POST /video/rag/ask endpoint contracts and 404 handling."""
        client = TestClient(app)

        # 1. Valid question
        payload = {
            "video_id": self.video_id,
            "question": "Can energy be lost as heat?",
            "timestamp": 25.0,
            "student_id": "student_1",
        }
        res = client.post("/video/rag/ask", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["video_id"], self.video_id)
        self.assertIn("answer", data)
        self.assertIsNotNone(data["active_scene"])
        self.assertEqual(data["active_scene"]["scene_number"], 2)
        self.assertIn("citations", data)
        self.assertIn("suggested_questions", data)

        # 2. Non-existent video returns 404
        bad_payload = {
            "video_id": "VID_non_existent_999",
            "question": "What is this video?",
        }
        bad_res = client.post("/video/rag/ask", json=bad_payload)
        self.assertEqual(bad_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
