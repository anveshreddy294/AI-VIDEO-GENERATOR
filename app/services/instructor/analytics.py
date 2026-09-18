"""Instructor Analytics & Human Intervention Portal Engine.

Aggregates student profiles, detects prerequisite bottlenecks, identifies students
flagged for human intervention via the anti-loop kill switch, and provides controls
for instructors to override or reset mastery statuses.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from ...core.config import settings
from ...services.assessment.profile import PROFILES_DIR, get_or_create_profile, save_profile
from ...services.assessment.schemas import ConceptMastery, StudentLearningProfile
from ...services.assessment.video_target import load_video_matrix, save_video_matrix
from ...services.registry import load_knowledge_graph
from .schemas import (
    CohortOverview,
    ConceptAnalytics,
    HumanInterventionAlert,
    ResetMasteryRequest,
    ResetMasteryResponse,
)

logger = logging.getLogger(__name__)


def get_all_student_profiles(source_id: Optional[str] = None) -> List[StudentLearningProfile]:
    """Scan and load all stored StudentLearningProfile records."""
    profiles: List[StudentLearningProfile] = []
    if not PROFILES_DIR.exists():
        return profiles

    for p_file in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(p_file.read_text(encoding="utf-8"))
            prof = StudentLearningProfile.model_validate(data)
            if source_id is None or prof.source_id == source_id:
                profiles.append(prof)
        except Exception as e:
            logger.warning("Could not load profile from %s: %s", p_file, e)

    return profiles


def get_cohort_overview(source_id: Optional[str] = None) -> CohortOverview:
    """Generate comprehensive cohort analytics and active human intervention alerts."""
    profiles = get_all_student_profiles(source_id)

    unique_students: Set[str] = set()
    unique_sources: Set[str] = set()
    alerts: List[HumanInterventionAlert] = []

    # Aggregation dictionaries: concept_id -> stats
    concept_totals: Dict[str, int] = defaultdict(int)
    concept_names: Dict[str, str] = {}
    mastered_counts: Dict[str, int] = defaultdict(int)
    learning_counts: Dict[str, int] = defaultdict(int)
    fallback_counts: Dict[str, int] = defaultdict(int)
    concept_sources: Dict[str, str] = {}

    total_mastery_scores: List[float] = []

    for prof in profiles:
        unique_students.add(prof.student_id)
        unique_sources.add(prof.source_id)

        # Cache KG for prerequisites
        kg = load_knowledge_graph(prof.source_id)

        for cid, mastery in prof.concept_masteries.items():
            concept_totals[cid] += 1
            concept_names[cid] = mastery.concept_name or cid
            concept_sources[cid] = prof.source_id

            status = mastery.status
            if status == "MASTERED":
                mastered_counts[cid] += 1
                total_mastery_scores.append(100.0)
            elif status in ("REQUIRES_HUMAN_FALLBACK", "REQUIRES_FALLBACK"):
                fallback_counts[cid] += 1
                total_mastery_scores.append(mastery.last_score)

                # Generate alert for human intervention
                prereqs = []
                if kg and kg.concepts and cid in kg.concepts:
                    prereqs = list(kg.concepts[cid].prerequisite_concept_ids or [])

                alerts.append(
                    HumanInterventionAlert(
                        student_id=prof.student_id,
                        source_id=prof.source_id,
                        concept_id=cid,
                        concept_name=mastery.concept_name or cid,
                        iteration_count=mastery.iteration_count,
                        last_score=round(mastery.last_score, 1),
                        last_attempt_at=mastery.last_attempt_at,
                        prerequisite_concept_ids=prereqs,
                        instructor_notes=getattr(mastery, "instructor_notes", None),
                    )
                )
            else:
                learning_counts[cid] += 1
                total_mastery_scores.append(mastery.last_score)

    # Detect prerequisite bottlenecks
    # A concept is a bottleneck if it's a prerequisite for others and has low mastery (<60%) or active fallbacks
    concept_analytics: List[ConceptAnalytics] = []
    for cid, total in concept_totals.items():
        m_cnt = mastered_counts[cid]
        l_cnt = learning_counts[cid]
        f_cnt = fallback_counts[cid]
        m_rate = round((m_cnt / total * 100.0) if total > 0 else 0.0, 1)

        # Check if prerequisite
        src_id = concept_sources.get(cid, "")
        kg = load_knowledge_graph(src_id) if src_id else None
        is_prereq = False
        if kg and kg.concepts:
            for other_cid, node in kg.concepts.items():
                if other_cid != cid and cid in (node.prerequisite_concept_ids or []):
                    is_prereq = True
                    break

        is_bottleneck = is_prereq and (f_cnt > 0 or m_rate < 60.0)

        concept_analytics.append(
            ConceptAnalytics(
                concept_id=cid,
                concept_name=concept_names.get(cid, cid),
                total_students=total,
                mastered_count=m_cnt,
                learning_count=l_cnt,
                fallback_count=f_cnt,
                mastery_rate_percent=m_rate,
                is_prerequisite_bottleneck=is_bottleneck,
            )
        )

    # Sort: bottlenecks & fallbacks first
    concept_analytics.sort(key=lambda x: (x.is_prerequisite_bottleneck, x.fallback_count, -x.mastery_rate_percent), reverse=True)
    alerts.sort(key=lambda a: (a.iteration_count, a.last_score), reverse=True)

    avg_mastery = round(sum(total_mastery_scores) / len(total_mastery_scores), 1) if total_mastery_scores else 0.0

    return CohortOverview(
        total_students=len(unique_students),
        total_sources=len(unique_sources),
        total_interventions_needed=len(alerts),
        average_mastery_percent=avg_mastery,
        alerts=alerts,
        concept_analytics=concept_analytics,
    )


def reset_student_concept_status(
    student_id: str,
    source_id: str,
    concept_id: str,
    new_status: str = "LEARNING",
    instructor_notes: Optional[str] = None,
) -> ResetMasteryResponse:
    """Instructor override action to resolve an alert or reset mastery for a concept."""
    profile = get_or_create_profile(student_id, source_id)
    if concept_id not in profile.concept_masteries:
        raise ValueError(f"Concept '{concept_id}' not found in student '{student_id}' profile.")

    mastery = profile.concept_masteries[concept_id]
    prev_status = mastery.status
    mastery.status = new_status

    if instructor_notes:
        mastery.instructor_notes = instructor_notes

    matrix = load_video_matrix(student_id, source_id)

    if new_status == "LEARNING":
        mastery.iteration_count = 0
        mastery.consecutive_correct = 0

        # Remove from human intervention list
        if matrix:
            if mastery.concept_name in matrix.human_intervention_concepts:
                matrix.human_intervention_concepts.remove(mastery.concept_name)
            if concept_id in matrix.human_intervention_concept_ids:
                matrix.human_intervention_concept_ids.remove(concept_id)
            if len(matrix.videos) == 0 and not matrix.human_intervention_concepts:
                matrix.decision = "ALL_MASTERED"
            save_video_matrix(matrix)

        message = f"Alert resolved: '{mastery.concept_name}' reset to LEARNING with 0 iterations for {student_id}."

    elif new_status == "MASTERED":
        mastery.correct_attempts = max(1, mastery.correct_attempts)
        mastery.consecutive_correct = max(1, mastery.consecutive_correct)

        # Update strong concepts
        if mastery.concept_name and mastery.concept_name not in profile.strong_concepts:
            profile.strong_concepts.append(mastery.concept_name)
        if concept_id not in profile.strong_concept_ids:
            profile.strong_concept_ids.append(concept_id)
        if mastery.concept_name in profile.weak_concepts:
            profile.weak_concepts.remove(mastery.concept_name)
        if concept_id in profile.weak_concept_ids:
            profile.weak_concept_ids.remove(concept_id)

        # Clean matrix
        if matrix:
            matrix.videos = [v for v in matrix.videos if v.concept_id != concept_id]
            if mastery.concept_name in matrix.human_intervention_concepts:
                matrix.human_intervention_concepts.remove(mastery.concept_name)
            if concept_id in matrix.human_intervention_concept_ids:
                matrix.human_intervention_concept_ids.remove(concept_id)
            if len(matrix.videos) == 0:
                matrix.decision = "ALL_MASTERED" if not matrix.human_intervention_concepts else "HUMAN_INTERVENTION"
            save_video_matrix(matrix)

        message = f"Instructor verified: '{mastery.concept_name}' marked as MASTERED for {student_id}."
    else:
        message = f"Status updated to '{new_status}' for {student_id}."

    save_profile(profile)

    return ResetMasteryResponse(
        student_id=student_id,
        source_id=source_id,
        concept_id=concept_id,
        previous_status=prev_status,
        new_status=new_status,
        message=message,
    )
