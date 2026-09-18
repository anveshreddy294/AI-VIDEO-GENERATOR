"""Comprehensive verification test suite for Instructor Analytics & Human Intervention Portal.

Verifies:
1. Human Intervention Alert Discovery: Scans profiles and detects kill-switch fallbacks.
2. Cohort Analytics & Prerequisite Bottleneck Detection: Calculates mastery percentages and flags bottlenecks.
3. Mastery Status Reset to LEARNING: Resets iterations to 0 and clears human intervention lists.
4. Manual Mastery Override to MASTERED: Verifies strong/weak list transitions and matrix resolution.
5. REST API Endpoints: Validates /instructor/api/overview, /instructor/api/reset-mastery, and HTML portal.
"""

import json
import shutil
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.main import app
from app.services.assessment.profile import PROFILES_DIR, get_or_create_profile, save_profile
from app.services.assessment.schemas import ConceptMastery, StudentLearningProfile, VideoTargetMatrix
from app.services.assessment.video_target import load_video_matrix, save_video_matrix
from app.services.instructor.analytics import get_cohort_overview, reset_student_concept_status
from app.services.instructor.schemas import CohortOverview, ResetMasteryResponse
from app.services.registry import save_knowledge_graph
from app.services.schemas import ConceptNode, KnowledgeGraph


class TestInstructorPortal(unittest.TestCase):
    def setUp(self):
        self.source_id = "SRC_instructor_test_01"
        self.student_a = "student_alice"
        self.student_b = "student_bob"
        self.student_c = "student_charlie"

        # 1. Seed KnowledgeGraph with prerequisite dependency
        # CONCEPT_MATH is prerequisite for CONCEPT_PHYSICS
        self.kg = KnowledgeGraph(
            concepts={
                "CONCEPT_MATH": ConceptNode(
                    concept_id="CONCEPT_MATH",
                    name="Calculus Foundations",
                    definition="Differential and integral calculus principles.",
                    prerequisite_concept_ids=[],
                ),
                "CONCEPT_PHYSICS": ConceptNode(
                    concept_id="CONCEPT_PHYSICS",
                    name="Classical Mechanics",
                    definition="Motion, forces, and kinematics governing physical systems.",
                    prerequisite_concept_ids=["CONCEPT_MATH"],
                ),
            }
        )
        save_knowledge_graph(self.source_id, self.kg)

        # 2. Seed Student Alice: Failed CONCEPT_MATH 4 times -> Hit Kill Switch (REQUIRES_HUMAN_FALLBACK)
        self.profile_a = StudentLearningProfile(
            student_id=self.student_a,
            source_id=self.source_id,
            weak_concepts=["Calculus Foundations"],
            weak_concept_ids=["CONCEPT_MATH"],
            concept_masteries={
                "CONCEPT_MATH": ConceptMastery(
                    concept_id="CONCEPT_MATH",
                    concept_name="Calculus Foundations",
                    attempts=4,
                    correct_attempts=0,
                    consecutive_correct=0,
                    iteration_count=4,
                    status="REQUIRES_HUMAN_FALLBACK",
                    last_score=25.0,
                )
            },
        )
        save_profile(self.profile_a)

        # Matrix for Alice with human intervention queue
        self.matrix_a = VideoTargetMatrix(
            session_id="SESS_A_01",
            student_id=self.student_a,
            source_id=self.source_id,
            decision="HUMAN_INTERVENTION",
            human_intervention_concepts=["Calculus Foundations"],
            human_intervention_concept_ids=["CONCEPT_MATH"],
            videos=[],
        )
        save_video_matrix(self.matrix_a)

        # 3. Seed Student Bob: In LEARNING for CONCEPT_MATH
        self.profile_b = StudentLearningProfile(
            student_id=self.student_b,
            source_id=self.source_id,
            weak_concepts=["Calculus Foundations"],
            weak_concept_ids=["CONCEPT_MATH"],
            concept_masteries={
                "CONCEPT_MATH": ConceptMastery(
                    concept_id="CONCEPT_MATH",
                    concept_name="Calculus Foundations",
                    attempts=2,
                    correct_attempts=0,
                    consecutive_correct=0,
                    iteration_count=2,
                    status="LEARNING",
                    last_score=50.0,
                )
            },
        )
        save_profile(self.profile_b)

        # 4. Seed Student Charlie: MASTERED CONCEPT_MATH and CONCEPT_PHYSICS
        self.profile_c = StudentLearningProfile(
            student_id=self.student_c,
            source_id=self.source_id,
            strong_concepts=["Calculus Foundations", "Classical Mechanics"],
            strong_concept_ids=["CONCEPT_MATH", "CONCEPT_PHYSICS"],
            concept_masteries={
                "CONCEPT_MATH": ConceptMastery(
                    concept_id="CONCEPT_MATH",
                    concept_name="Calculus Foundations",
                    attempts=2,
                    correct_attempts=2,
                    consecutive_correct=2,
                    status="MASTERED",
                    last_score=100.0,
                ),
                "CONCEPT_PHYSICS": ConceptMastery(
                    concept_id="CONCEPT_PHYSICS",
                    concept_name="Classical Mechanics",
                    attempts=1,
                    correct_attempts=1,
                    consecutive_correct=1,
                    status="MASTERED",
                    last_score=100.0,
                ),
            },
        )
        save_profile(self.profile_c)

    def test_1_human_intervention_alert_discovery(self):
        """Test 1: Verify detection of students trapped in REQUIRES_HUMAN_FALLBACK."""
        overview = get_cohort_overview(source_id=self.source_id)

        self.assertGreaterEqual(overview.total_students, 3)
        self.assertEqual(overview.total_interventions_needed, 1)
        self.assertEqual(len(overview.alerts), 1)

        alert = overview.alerts[0]
        self.assertEqual(alert.student_id, self.student_a)
        self.assertEqual(alert.concept_id, "CONCEPT_MATH")
        self.assertEqual(alert.iteration_count, 4)
        self.assertEqual(alert.last_score, 25.0)

    def test_2_cohort_aggregation_and_bottleneck_detection(self):
        """Test 2: Verify cohort mastery metrics and prerequisite bottleneck identification."""
        overview = get_cohort_overview(source_id=self.source_id)

        # CONCEPT_MATH is a prerequisite for CONCEPT_PHYSICS and has fallbacks + low mastery
        math_analytics = next((c for c in overview.concept_analytics if c.concept_id == "CONCEPT_MATH"), None)
        self.assertIsNotNone(math_analytics)
        self.assertEqual(math_analytics.total_students, 3)
        self.assertEqual(math_analytics.mastered_count, 1)   # Charlie
        self.assertEqual(math_analytics.learning_count, 1)   # Bob
        self.assertEqual(math_analytics.fallback_count, 1)   # Alice
        self.assertAlmostEqual(math_analytics.mastery_rate_percent, 33.3, delta=0.5)
        # Should be flagged as a bottleneck!
        self.assertTrue(math_analytics.is_prerequisite_bottleneck)

        # CONCEPT_PHYSICS is only taken by Charlie and mastered
        phys_analytics = next((c for c in overview.concept_analytics if c.concept_id == "CONCEPT_PHYSICS"), None)
        self.assertIsNotNone(phys_analytics)
        self.assertEqual(phys_analytics.mastered_count, 1)
        self.assertEqual(phys_analytics.fallback_count, 0)
        self.assertFalse(phys_analytics.is_prerequisite_bottleneck)

    def test_3_mastery_status_reset_to_learning(self):
        """Test 3: Verify instructor can reset status to LEARNING, clearing kill switch."""
        res = reset_student_concept_status(
            student_id=self.student_a,
            source_id=self.source_id,
            concept_id="CONCEPT_MATH",
            new_status="LEARNING",
            instructor_notes="Reviewed concept 1-on-1 with Alice.",
        )

        self.assertIsInstance(res, ResetMasteryResponse)
        self.assertEqual(res.new_status, "LEARNING")
        self.assertEqual(res.previous_status, "REQUIRES_HUMAN_FALLBACK")

        # Verify profile updated
        updated_prof = get_or_create_profile(self.student_a, self.source_id)
        mastery = updated_prof.concept_masteries["CONCEPT_MATH"]
        self.assertEqual(mastery.status, "LEARNING")
        self.assertEqual(mastery.iteration_count, 0)  # Reset to 0!

        # Verify matrix cleared from human intervention
        matrix = load_video_matrix(self.student_a, self.source_id)
        self.assertNotIn("Calculus Foundations", matrix.human_intervention_concepts)
        self.assertNotIn("CONCEPT_MATH", matrix.human_intervention_concept_ids)

        # Re-run overview -> 0 alerts remaining for this source
        new_overview = get_cohort_overview(source_id=self.source_id)
        self.assertEqual(new_overview.total_interventions_needed, 0)

    def test_4_manual_mastery_override_to_mastered(self):
        """Test 4: Verify instructor manual override to MASTERED."""
        res = reset_student_concept_status(
            student_id=self.student_b,
            source_id=self.source_id,
            concept_id="CONCEPT_MATH",
            new_status="MASTERED",
            instructor_notes="Demonstrated mastery during office hours.",
        )

        self.assertEqual(res.new_status, "MASTERED")

        # Verify profile
        updated_prof = get_or_create_profile(self.student_b, self.source_id)
        self.assertIn("Calculus Foundations", updated_prof.strong_concepts)
        self.assertNotIn("Calculus Foundations", updated_prof.weak_concepts)
        self.assertEqual(updated_prof.concept_masteries["CONCEPT_MATH"].status, "MASTERED")

    def test_5_rest_api_endpoints(self):
        """Test 5: REST API contracts for overview, reset, and HTML dashboard."""
        import os
        # SEC-003: Set INSTRUCTOR_API_KEY for test so the auth guard can validate
        test_key = "test-instructor-key-for-unit-tests"
        os.environ["INSTRUCTOR_API_KEY"] = test_key
        auth_headers = {"X-Instructor-Key": test_key}
        client = TestClient(app)

        # 1. GET /instructor/api/overview (with auth header)
        overview_res = client.get(f"/instructor/api/overview?source_id={self.source_id}", headers=auth_headers)
        self.assertEqual(overview_res.status_code, 200)
        overview_data = overview_res.json()
        self.assertIn("total_students", overview_data)
        self.assertIn("alerts", overview_data)
        self.assertIn("concept_analytics", overview_data)

        # 1b. Verify auth guard blocks unauthenticated access
        unauth_res = client.get(f"/instructor/api/overview?source_id={self.source_id}")
        self.assertIn(unauth_res.status_code, (401, 403), "Unauthenticated request must be rejected")

        # 2. POST /instructor/api/reset-mastery (with auth header)
        reset_payload = {
            "student_id": self.student_a,
            "source_id": self.source_id,
            "concept_id": "CONCEPT_MATH",
            "new_status": "LEARNING",
            "instructor_notes": "API test reset",
        }
        post_res = client.post("/instructor/api/reset-mastery", json=reset_payload, headers=auth_headers)
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.json()
        self.assertEqual(post_data["new_status"], "LEARNING")

        # 2b. Verify invalid status is rejected by Pydantic Literal constraint (SEC-008)
        bad_status_payload = {**reset_payload, "new_status": "HACKED"}
        bad_res = client.post("/instructor/api/reset-mastery", json=bad_status_payload, headers=auth_headers)
        self.assertEqual(bad_res.status_code, 422, "Invalid new_status must be rejected with 422 Unprocessable Entity")

        # 3. GET /instructor (HTML UI â€” no auth required for the web page itself)
        html_res = client.get("/instructor")
        self.assertEqual(html_res.status_code, 200)
        self.assertIn("VisualAI Instructor Portal", html_res.text)
        self.assertIn("kpiInterventions", html_res.text)

        # Cleanup
        del os.environ["INSTRUCTOR_API_KEY"]


if __name__ == "__main__":
    unittest.main()
