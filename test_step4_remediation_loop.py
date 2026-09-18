"""Comprehensive test suite for Step 4 Remediation Verification & Re-Testing Loop.

Verifies:
1. Generate remediation check session: Questions are grounded, answer keys hidden (SafeQuestion).
2. Evaluate failed submission: iteration_count increments, status remains LEARNING.
3. Evaluate passed submission: Concept transitions to MASTERED, removed from VideoTargetMatrix, profile updated.
4. Anti-loop kill switch: Repeated failures (>3) transition status to REQUIRES_HUMAN_FALLBACK and update human intervention list.
5. End-to-end REST API integration test: /remediation/start and /remediation/submit with full contracts.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.assessment.profile import get_or_create_profile, save_profile
from app.services.assessment.schemas import (
    AnswerSubmission,
    ConceptMastery,
    SafeQuestion,
    StudentLearningProfile,
    VideoTarget,
    VideoTargetMatrix,
)
from app.services.assessment.session_store import load_session
from app.services.assessment.video_target import load_video_matrix, save_video_matrix
from app.services.registry import save_content_units, save_knowledge_graph
from app.services.remediation.engine import (
    create_remediation_session,
    evaluate_remediation_submission,
)
from app.services.schemas import ConceptNode, ContentUnit, KnowledgeGraph


class TestStep4RemediationLoop(unittest.TestCase):
    def setUp(self):
        self.student_id = "test_student_step4"
        self.source_id = "SRC_test_step4_src"
        self.concept_id = "CONCEPT_MOMENTUM"
        self.concept_name = "Conservation of Momentum"

        # 1. Seed Knowledge Graph
        self.kg = KnowledgeGraph(
            concepts={
                self.concept_id: ConceptNode(
                    concept_id=self.concept_id,
                    name=self.concept_name,
                    definition="The total momentum of an isolated system remains constant if no external forces act on it.",
                    prerequisite_concept_ids=[],
                    source_content_ids=["CU_MOM_01"],
                )
            }
        )
        save_knowledge_graph(self.source_id, self.kg)

        # 2. Seed ContentUnits for grounding
        save_content_units(
            self.source_id,
            [
                ContentUnit(
                    content_id="CU_MOM_01",
                    source_id=self.source_id,
                    asset_id="AST_step4",
                    extraction_method="direct",
                    modality="txt",
                    text=(
                        "Conservation of Momentum: For a collision occurring between object 1 and object 2 "
                        "in an isolated system, the total momentum of the two objects before the collision "
                        "is equal to the total momentum of the two objects after the collision."
                    ),
                    page=1,
                    token_count=45,
                )
            ],
        )

        # 3. Seed StudentLearningProfile with weak concept
        self.profile = StudentLearningProfile(
            student_id=self.student_id,
            source_id=self.source_id,
            weak_concepts=[self.concept_name],
            weak_concept_ids=[self.concept_id],
            strong_concepts=[],
            strong_concept_ids=[],
            concept_masteries={
                self.concept_id: ConceptMastery(
                    concept_id=self.concept_id,
                    concept_name=self.concept_name,
                    attempts=1,
                    correct_attempts=0,
                    consecutive_correct=0,
                    iteration_count=1,
                    status="LEARNING",
                    last_score=0.0,
                )
            },
        )
        save_profile(self.profile)

        # 4. Seed VideoTargetMatrix with 1 active remediation target
        self.matrix = VideoTargetMatrix(
            session_id="SESS_PREV_01",
            student_id=self.student_id,
            source_id=self.source_id,
            decision="GENERATE_VIDEOS",
            summary=f"Generate a 45-second video explaining {self.concept_name}.",
            videos=[
                VideoTarget(
                    session_id="SESS_PREV_01",
                    student_id=self.student_id,
                    source_id=self.source_id,
                    concept_id=self.concept_id,
                    concept_name=self.concept_name,
                    directive=f"Explain {self.concept_name}",
                    target_seconds=45,
                    difficulty="intermediate",
                )
            ],
        )
        save_video_matrix(self.matrix)

    def test_1_generate_remediation_session_grounded_and_safe(self):
        """Test 1: Verify verification session creates grounded questions and hidden answer keys."""
        session, safe_questions = create_remediation_session(
            student_id=self.student_id,
            source_id=self.source_id,
            concept_id=self.concept_id,
            count=1,
            mock_mode=True,
        )

        # 1. Verify session persisted
        self.assertIsNotNone(session.session_id)
        persisted_session = load_session(session.session_id)
        self.assertIsNotNone(persisted_session)
        self.assertEqual(len(persisted_session.questions), 1)

        # 2. Verify questions are grounded
        stored_q = persisted_session.questions[0]
        self.assertEqual(stored_q.concept_id, self.concept_id)
        self.assertIn(self.concept_name, stored_q.concept_name)
        self.assertGreaterEqual(len(stored_q.options), 4)
        self.assertIn(stored_q.correct_index, [0, 1, 2, 3])

        # 3. Verify SafeQuestion contract (Hidden answers protection)
        self.assertEqual(len(safe_questions), 1)
        safe_q = safe_questions[0]
        self.assertIsInstance(safe_q, SafeQuestion)
        self.assertEqual(safe_q.question_id, stored_q.question_id)
        self.assertEqual(safe_q.stem, stored_q.stem)
        self.assertEqual(len(safe_q.options), 4)

        # Critical security check: SafeQuestion schema must not expose answer keys
        safe_dict = safe_q.model_dump()
        self.assertNotIn("correct_index", safe_dict)
        self.assertNotIn("explanation", safe_dict)

    def test_2_evaluate_failed_submission_increments_iteration(self):
        """Test 2: Verify failed submission increments iteration_count and keeps status LEARNING."""
        session, _ = create_remediation_session(
            student_id=self.student_id,
            source_id=self.source_id,
            concept_id=self.concept_id,
            count=1,
            mock_mode=True,
        )
        stored_q = session.questions[0]
        # Choose wrong index
        wrong_index = (stored_q.correct_index + 1) % len(stored_q.options)

        submission_answers = [
            AnswerSubmission(question_id=stored_q.question_id, selected_index=wrong_index)
        ]

        result = evaluate_remediation_submission(
            session_id=session.session_id,
            student_id=self.student_id,
            concept_id=self.concept_id,
            answers=submission_answers,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["new_status"], "LEARNING")
        self.assertIn("not yet mastered", result["message"].lower())

        # Check updated profile
        updated_profile = get_or_create_profile(self.student_id, self.source_id)
        mastery = updated_profile.concept_masteries[self.concept_id]
        self.assertEqual(mastery.status, "LEARNING")
        self.assertEqual(mastery.consecutive_correct, 0)
        self.assertEqual(mastery.iteration_count, 2)  # was 1, incremented to 2
        self.assertIn(self.concept_name, updated_profile.weak_concepts)
        self.assertNotIn(self.concept_name, updated_profile.strong_concepts)

    def test_3_evaluate_passed_submission_transitions_to_mastered(self):
        """Test 3: Verify passed submission transitions to MASTERED and resolves VideoTargetMatrix."""
        session, _ = create_remediation_session(
            student_id=self.student_id,
            source_id=self.source_id,
            concept_id=self.concept_id,
            count=1,
            mock_mode=True,
        )
        stored_q = session.questions[0]
        correct_index = stored_q.correct_index

        submission_answers = [
            AnswerSubmission(question_id=stored_q.question_id, selected_index=correct_index)
        ]

        result = evaluate_remediation_submission(
            session_id=session.session_id,
            student_id=self.student_id,
            concept_id=self.concept_id,
            answers=submission_answers,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["percentage"], 100.0)
        self.assertEqual(result["previous_status"], "LEARNING")
        self.assertEqual(result["new_status"], "MASTERED")
        self.assertIn("congratulations", result["message"].lower())

        # Check profile updates
        updated_profile = get_or_create_profile(self.student_id, self.source_id)
        mastery = updated_profile.concept_masteries[self.concept_id]
        self.assertEqual(mastery.status, "MASTERED")
        self.assertGreaterEqual(mastery.correct_attempts, 1)
        self.assertGreaterEqual(mastery.consecutive_correct, 1)
        self.assertIn(self.concept_name, updated_profile.strong_concepts)
        self.assertNotIn(self.concept_name, updated_profile.weak_concepts)

        # Check VideoTargetMatrix resolution
        updated_matrix = load_video_matrix(self.student_id, self.source_id)
        self.assertIsNotNone(updated_matrix)
        # Resolved target removed
        self.assertEqual(len(updated_matrix.videos), 0)
        self.assertEqual(updated_matrix.decision, "ALL_MASTERED")
        self.assertIn("All assessed concepts", updated_matrix.summary)

    def test_4_anti_loop_kill_switch_triggers_human_fallback(self):
        """Test 4: Verify failing remediation check >3 times locks concept to REQUIRES_HUMAN_FALLBACK."""
        # Set iteration_count = 3 (at threshold)
        profile = get_or_create_profile(self.student_id, self.source_id)
        profile.concept_masteries[self.concept_id].iteration_count = settings.kill_switch_limit
        save_profile(profile)

        session, _ = create_remediation_session(
            student_id=self.student_id,
            source_id=self.source_id,
            concept_id=self.concept_id,
            count=1,
            mock_mode=True,
        )
        stored_q = session.questions[0]
        wrong_index = (stored_q.correct_index + 1) % len(stored_q.options)

        # Student fails a 4th time (> kill_switch_limit=3)
        result = evaluate_remediation_submission(
            session_id=session.session_id,
            student_id=self.student_id,
            concept_id=self.concept_id,
            answers=[AnswerSubmission(question_id=stored_q.question_id, selected_index=wrong_index)],
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["new_status"], "REQUIRES_HUMAN_FALLBACK")
        self.assertIn("instructor intervention", result["message"].lower())

        # Check profile
        updated_profile = get_or_create_profile(self.student_id, self.source_id)
        mastery = updated_profile.concept_masteries[self.concept_id]
        self.assertEqual(mastery.status, "REQUIRES_HUMAN_FALLBACK")
        self.assertGreater(mastery.iteration_count, settings.kill_switch_limit)

        # Check VideoTargetMatrix
        updated_matrix = load_video_matrix(self.student_id, self.source_id)
        self.assertIn(self.concept_name, updated_matrix.human_intervention_concepts)
        self.assertEqual(len(updated_matrix.videos), 0)
        self.assertEqual(updated_matrix.decision, "HUMAN_INTERVENTION")

    def test_5_end_to_end_rest_api_remediation(self):
        """Test 5: REST API integration test for /remediation/start and /remediation/submit."""
        client = TestClient(app)

        # 1. Test POST /remediation/start
        start_payload = {
            "student_id": self.student_id,
            "source_id": self.source_id,
            "concept_id": self.concept_id,
            "count": 1,
        }
        res = client.post("/remediation/start", json=start_payload)
        self.assertEqual(res.status_code, 200)
        start_data = res.json()
        self.assertIn("session_id", start_data)
        self.assertEqual(start_data["concept_id"], self.concept_id)
        self.assertEqual(len(start_data["questions"]), 1)

        safe_q = start_data["questions"][0]
        self.assertIn("question_id", safe_q)
        self.assertIn("stem", safe_q)
        self.assertIn("options", safe_q)
        self.assertNotIn("correct_index", safe_q)
        self.assertNotIn("explanation", safe_q)

        # 2. Retrieve session from backend to determine correct index
        persisted_session = load_session(start_data["session_id"])
        correct_index = persisted_session.questions[0].correct_index

        # 3. Test POST /remediation/submit
        submit_payload = {
            "session_id": start_data["session_id"],
            "student_id": self.student_id,
            "concept_id": self.concept_id,
            "answers": [
                {
                    "question_id": safe_q["question_id"],
                    "selected_index": correct_index,
                }
            ],
        }
        sub_res = client.post("/remediation/submit", json=submit_payload)
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.json()

        self.assertTrue(sub_data["passed"])
        self.assertEqual(sub_data["new_status"], "MASTERED")
        self.assertEqual(sub_data["score"], 1)
        self.assertIn("profile_summary", sub_data)
        self.assertIn(self.concept_name, sub_data["profile_summary"]["strong_concepts"])
        self.assertNotIn(self.concept_name, sub_data["profile_summary"]["weak_concepts"])


if __name__ == "__main__":
    unittest.main()
