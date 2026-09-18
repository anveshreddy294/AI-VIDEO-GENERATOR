"""Verification test suite for Step 2 -> Step 3 Remediation Contract Hardening.

Verifies:
1. One incorrect question -> exactly one corresponding remediation target.
2. All correct -> ALL_MASTERED decision with empty video targets.
3. Old weak concept from older session NOT tested in current session -> strictly excluded from videos.
4. Prerequisite failure -> proper prerequisite concept IDs and gap analysis included.
5. Exact Qdrant chunk provenance recovered via deterministic filter.
6. Missing chunk in vector DB -> controlled fallback to ContentUnits without hallucination.
7. Anti-loop kill switch (>3 failed attempts) -> routed to human intervention, excluded from videos.
8. Hidden answers protection -> SafeQuestion never reveals correct_index or explanation before submission.
9. Persistence isolation -> Video targets persisted strictly in storage/runtime/video_targets/.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.db.vector_store import retrieve_exact_chunks
from app.services.assessment.engine import grade_submission
from app.services.assessment.schemas import (
    AnswerSubmission,
    AssessmentOption,
    AssessmentSession,
    ConceptMastery,
    ConceptSnapshot,
    Question,
    QuestionResult,
    SafeOption,
    SafeQuestion,
    StudentLearningProfile,
    StudentSubmission,
    SubmissionResult,
    VideoTargetMatrix,
)
from app.services.assessment.video_target import (
    build_video_target_matrix,
    load_video_matrix,
    save_video_matrix,
)
from app.services.registry import save_content_units
from app.services.schemas import ConceptNode, ContentUnit, KnowledgeGraph, RichChunk


class TestStep2ToStep3RemediationContract(unittest.TestCase):
    def setUp(self):
        self.student_id = "test_student_remediation"
        self.source_id = "SRC_test_remediation_src"

        # Build KnowledgeGraph with concepts: Concept A (Parent), Concept B (Child with prereq Concept A), Concept C (Independent)
        self.kg = KnowledgeGraph(
            concepts={
                "CONCEPT_A": ConceptNode(
                    concept_id="CONCEPT_A",
                    name="Newton's First Law",
                    definition="An object remains at rest or in uniform motion unless acted upon by a force.",
                    prerequisite_concept_ids=[],
                    source_content_ids=["CU_001"],
                ),
                "CONCEPT_B": ConceptNode(
                    concept_id="CONCEPT_B",
                    name="Inertia",
                    definition="The resistance of any physical object to any change in its velocity.",
                    prerequisite_concept_ids=["CONCEPT_A"],
                    source_content_ids=["CU_002"],
                ),
                "CONCEPT_C": ConceptNode(
                    concept_id="CONCEPT_C",
                    name="Momentum",
                    definition="The quantity of motion of a moving body, measured as a product of its mass and velocity.",
                    prerequisite_concept_ids=[],
                    source_content_ids=["CU_003"],
                ),
                "CONCEPT_OLD_WEAK": ConceptNode(
                    concept_id="CONCEPT_OLD_WEAK",
                    name="Centripetal Force",
                    definition="A force that acts on a body moving in a circular path and is directed toward the center.",
                    prerequisite_concept_ids=[],
                    source_content_ids=["CU_OLD"],
                ),
            }
        )

        # Seed ContentUnits in registry for fallback resolution
        save_content_units(
            self.source_id,
            [
                ContentUnit(
                    content_id="CU_001",
                    source_id=self.source_id,
                    asset_id="AST_test",
                    extraction_method="direct",
                    modality="txt",
                    text="Newton's First Law: An object continues in a state of rest unless acted upon by a net external force.",
                ),
                ContentUnit(
                    content_id="CU_002",
                    source_id=self.source_id,
                    asset_id="AST_test",
                    extraction_method="direct",
                    modality="txt",
                    text="Inertia is the inherent property of matter that quantifies resistance to acceleration.",
                ),
                ContentUnit(
                    content_id="CU_003",
                    source_id=self.source_id,
                    asset_id="AST_test",
                    extraction_method="direct",
                    modality="txt",
                    text="Momentum equals mass multiplied by velocity.",
                ),
            ],
        )

    def _create_sample_session(self, test_concept_ids: list[str]) -> AssessmentSession:
        """Helper to create an AssessmentSession with questions testing specified concepts."""
        questions: list[Question] = []
        for i, cid in enumerate(test_concept_ids):
            concept = self.kg.concepts[cid]
            q = Question(
                question_id=f"Q_{cid}_{i}",
                concept_id=cid,
                concept_name=concept.name,
                stem=f"What is the fundamental principle of {concept.name}?",
                options=[
                    AssessmentOption(index=0, text="Incorrect distractor A"),
                    AssessmentOption(index=1, text=f"Correct definition of {concept.name}"),
                    AssessmentOption(index=2, text="Incorrect distractor B"),
                    AssessmentOption(index=3, text="Incorrect distractor C"),
                ],
                correct_index=1,
                explanation=f"Option 1 is correct because {concept.definition}",
                chunk_ids=[f"CHUNK_{cid}"],
                content_ids=list(concept.source_content_ids),
                page_start=10 + i,
                page_end=11 + i,
                source_id=self.source_id,
                difficulty="intermediate",
            )
            questions.append(q)

        session = AssessmentSession(
            session_id=f"SESS_TEST_{datetime.now(timezone.utc).timestamp()}",
            student_id=self.student_id,
            source_id=self.source_id,
            questions=questions,
            status="READY",
        )
        return session

    def test_1_one_incorrect_question_generates_one_targeted_remediation(self):
        """Scenario 1: One incorrect question produces exactly one enriched VideoTarget."""
        session = self._create_sample_session(["CONCEPT_A", "CONCEPT_C"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Answer CONCEPT_A incorrectly (selected 0), CONCEPT_C correctly (selected 1)
        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
                AnswerSubmission(question_id=session.questions[1].question_id, selected_index=1),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        self.assertEqual(matrix.decision, "GENERATE_VIDEOS")
        self.assertEqual(len(matrix.videos), 1)

        target = matrix.videos[0]
        self.assertEqual(target.concept_id, "CONCEPT_A")
        self.assertEqual(target.concept_name, "Newton's First Law")
        self.assertEqual(target.selected_index, 0)
        self.assertEqual(target.correct_index, 1)
        self.assertEqual(target.question_id, session.questions[0].question_id)
        self.assertIn("Incorrect distractor A", target.misconception)
        self.assertIn("Correct definition of Newton's First Law", target.misconception)
        self.assertIn("CU_001", target.source_content_ids)
        self.assertEqual(target.page_start, 10)
        self.assertEqual(target.difficulty, "foundational")
        self.assertEqual(target.target_seconds, 30)  # foundational (0 prereqs) = 30s
        self.assertTrue(len(target.authoritative_evidence) > 0)
        self.assertEqual(target.scope, "current_session")
        print("   [PASS] Scenario 1: One incorrect question -> exactly one corresponding remediation target.")

    def test_2_all_correct_yields_all_mastered_with_zero_video_targets(self):
        """Scenario 2: All correct answers in current session yields ALL_MASTERED."""
        session = self._create_sample_session(["CONCEPT_A", "CONCEPT_C"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Both correct
        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=1),
                AnswerSubmission(question_id=session.questions[1].question_id, selected_index=1),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        self.assertEqual(matrix.decision, "ALL_MASTERED")
        self.assertEqual(len(matrix.videos), 0)
        self.assertIn("All assessed concepts", matrix.summary)
        print("   [PASS] Scenario 2: All correct -> ALL_MASTERED with zero video targets.")

    def test_3_older_weak_concept_not_tested_is_strictly_excluded(self):
        """Scenario 3: An older weak concept NOT in current session is not inserted into videos."""
        session = self._create_sample_session(["CONCEPT_C"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Seed older weak concept in profile from prior session
        profile.concept_masteries["CONCEPT_OLD_WEAK"] = ConceptMastery(
            concept_id="CONCEPT_OLD_WEAK",
            concept_name="Centripetal Force",
            attempts=1,
            correct_attempts=0,
            consecutive_correct=0,
            status="LEARNING",
            last_score=0.0,
        )

        # Current session tests ONLY CONCEPT_C and answers correctly
        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=1),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
            include_historical=False,
        )

        # Videos must be strictly empty because current session passed 100%
        self.assertEqual(matrix.decision, "ALL_MASTERED")
        self.assertEqual(len(matrix.videos), 0)
        # Check that CONCEPT_OLD_WEAK was NOT inserted
        self.assertFalse(any(v.concept_id == "CONCEPT_OLD_WEAK" for v in matrix.videos))

        # If include_historical=True, it appears in historical_review_videos, NOT matrix.videos
        matrix_hist = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
            include_historical=True,
        )
        self.assertEqual(len(matrix_hist.videos), 0)
        self.assertEqual(len(matrix_hist.historical_review_videos), 1)
        self.assertEqual(matrix_hist.historical_review_videos[0].concept_id, "CONCEPT_OLD_WEAK")
        self.assertEqual(matrix_hist.historical_review_videos[0].scope, "historical_review")
        print("   [PASS] Scenario 3: Older weak concept not tested in current session is strictly isolated.")

    def test_4_prerequisite_failure_context_included(self):
        """Scenario 4: Child concept failed with failed prerequisite captures gap context."""
        # Session tests both parent (CONCEPT_A) and child (CONCEPT_B)
        session = self._create_sample_session(["CONCEPT_A", "CONCEPT_B"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Student fails BOTH parent (CONCEPT_A) and child (CONCEPT_B)
        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
                AnswerSubmission(question_id=session.questions[1].question_id, selected_index=0),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        self.assertEqual(len(matrix.videos), 2)
        target_b = next(v for v in matrix.videos if v.concept_id == "CONCEPT_B")
        self.assertIn("CONCEPT_A", target_b.prerequisite_concept_ids)
        self.assertIn("CONCEPT_A", target_b.prerequisite_gaps)
        print("   [PASS] Scenario 4: Prerequisite failure properly tracked in prerequisite_gaps.")

    def test_5_missing_qdrant_chunk_fallback_to_content_units(self):
        """Scenario 5: If Qdrant returns no chunks, fallback uses ContentUnits without hallucination."""
        session = self._create_sample_session(["CONCEPT_A"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Question has chunk_id that does not exist in Qdrant
        session.questions[0].chunk_ids = ["NON_EXISTENT_CHUNK_XYZ"]

        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        self.assertEqual(len(matrix.videos), 1)
        target = matrix.videos[0]
        # Evidence must contain the exact ground truth text from CU_001
        self.assertTrue(len(target.authoritative_evidence) > 0)
        self.assertTrue(
            any("Newton's First Law" in ev for ev in target.authoritative_evidence),
            "Expected ContentUnit ground truth in authoritative evidence",
        )
        print("   [PASS] Scenario 5: Missing Qdrant chunk gracefully falls back to ContentUnits.")

    def test_5b_exact_qdrant_chunk_provenance_recovered(self):
        """Scenario 5b: Exact Qdrant chunks are deterministically recovered and prioritized."""
        from unittest.mock import patch

        session = self._create_sample_session(["CONCEPT_A"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)

        mock_payload = [{
            "chunk_id": "CHUNK_CONCEPT_A",
            "source_id": self.source_id,
            "concept_ids": ["CONCEPT_A"],
            "text": "Exact authoritative textbook chunk retrieved from Qdrant vector database.",
        }]

        with patch("app.db.vector_store.retrieve_exact_chunks", return_value=mock_payload) as mock_retrieve:
            matrix = build_video_target_matrix(
                profile=profile,
                kg=self.kg,
                session=session,
                submission_result=result,
            )

            mock_retrieve.assert_called_once()
            self.assertEqual(len(matrix.videos), 1)
            target = matrix.videos[0]
            self.assertIn("Exact authoritative textbook chunk retrieved from Qdrant vector database.", target.authoritative_evidence)
            print("   [PASS] Scenario 5b: Exact Qdrant chunk provenance recovered and prioritized.")

    def test_6_kill_switch_behavior_respected(self):
        """Scenario 6: Concepts with iteration_count > kill_switch_limit hit kill switch."""
        session = self._create_sample_session(["CONCEPT_A"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        # Pre-set CONCEPT_A to have failed 3 times historically
        profile.concept_masteries["CONCEPT_A"] = ConceptMastery(
            concept_id="CONCEPT_A",
            concept_name="Newton's First Law",
            attempts=3,
            correct_attempts=0,
            consecutive_correct=0,
            iteration_count=3,
            status="LEARNING",
            last_score=0.0,
        )

        # Student fails CONCEPT_A a 4th time (> kill_switch_limit=3)
        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        self.assertEqual(profile.concept_masteries["CONCEPT_A"].status, "REQUIRES_HUMAN_FALLBACK")

        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        # Concept on kill switch must NOT be in videos
        self.assertEqual(len(matrix.videos), 0)
        self.assertIn("CONCEPT_A", matrix.human_intervention_concept_ids)
        self.assertEqual(matrix.decision, "HUMAN_INTERVENTION")
        print("   [PASS] Scenario 6: Anti-loop kill switch routed to human intervention, excluded from videos.")

    def test_7_safe_questions_never_expose_answers_pre_submission(self):
        """Scenario 7: SafeQuestion strips correct_index and explanation."""
        session = self._create_sample_session(["CONCEPT_A"])
        raw_q = session.questions[0]

        # Convert to SafeQuestion
        safe_q = SafeQuestion(
            question_id=raw_q.question_id,
            concept_id=raw_q.concept_id,
            concept_name=raw_q.concept_name,
            stem=raw_q.stem,
            options=[SafeOption(index=opt.index, text=opt.text) for opt in raw_q.options],
            difficulty=raw_q.difficulty,
            page_start=raw_q.page_start,
            page_end=raw_q.page_end,
            chunk_ids=raw_q.chunk_ids,
        )

        safe_dict = safe_q.model_dump()
        self.assertNotIn("correct_index", safe_dict)
        self.assertNotIn("explanation", safe_dict)
        self.assertEqual(len(safe_q.options), 4)
        print("   [PASS] Scenario 7: SafeQuestion protects answer keys and explanations pre-submission.")

    def test_8_persistence_in_runtime_storage(self):
        """Scenario 8: VideoTargetMatrix is saved strictly to storage/runtime/video_targets/."""
        session = self._create_sample_session(["CONCEPT_A"])
        profile = StudentLearningProfile(student_id=self.student_id, source_id=self.source_id)

        submission = StudentSubmission(
            session_id=session.session_id,
            answers=[
                AnswerSubmission(question_id=session.questions[0].question_id, selected_index=0),
            ],
        )

        result = grade_submission(submission, session, self.kg, profile)
        matrix = build_video_target_matrix(
            profile=profile,
            kg=self.kg,
            session=session,
            submission_result=result,
        )

        out_path = save_video_matrix(matrix)
        self.assertTrue(out_path.exists())
        self.assertTrue(
            "storage\\runtime\\video_targets" in str(out_path) or "storage/runtime/video_targets" in str(out_path),
            f"Expected out_path in storage/runtime/video_targets, got: {out_path}",
        )

        loaded = load_video_matrix(self.student_id, self.source_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.decision, matrix.decision)
        print("   [PASS] Scenario 8: Video matrix persisted strictly to runtime storage and reloaded.")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("   TESTING STEP 2 -> STEP 3 REMEDIATION CONTRACT HARDENING   ")
    print("=" * 65 + "\n")
    unittest.main(verbosity=1)
