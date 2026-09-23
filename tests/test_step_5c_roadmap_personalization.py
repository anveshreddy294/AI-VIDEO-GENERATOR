"""Unit, isolation, and policy tests for Step 5C: Learning Roadmap and Next-Action Selection."""

import pytest
from app.services.mastery import (
    ConceptDependencyProvider,
    DomainInvariantViolation,
    GroundingIntegrityError,
    InMemoryMasteryRepository,
    LearningActionType,
    LearningRoadmap,
    MasteryConfig,
    MasteryRecord,
    MasteryState,
    MasteryStateMachine,
    NextLearningAction,
    PersonalizationService,
    ReasonCode,
)
from app.services.schemas import ConceptNode, KnowledgeGraph


@pytest.fixture
def repo() -> InMemoryMasteryRepository:
    return InMemoryMasteryRepository()


@pytest.fixture
def sm() -> MasteryStateMachine:
    return MasteryStateMachine(MasteryConfig())


@pytest.fixture
def sample_kg() -> KnowledgeGraph:
    """A grounded knowledge graph with 4 concepts:

    C_A (Foundations: Mass & Force)
    C_B (Newton's Second Law, depends on C_A)
    C_C (Newton's Third Law, independent)
    C_D (Conservation of Momentum, depends on C_B)
    """
    return KnowledgeGraph(
        concepts={
            "C_A": ConceptNode(
                concept_id="C_A",
                name="Mass and Force",
                definition="Fundamental definitions of mass and force.",
                prerequisite_concept_ids=[],
            ),
            "C_B": ConceptNode(
                concept_id="C_B",
                name="Newton's Second Law",
                definition="F = ma relating net force, mass, and acceleration.",
                prerequisite_concept_ids=["C_A"],
            ),
            "C_C": ConceptNode(
                concept_id="C_C",
                name="Newton's Third Law",
                definition="Action and reaction forces.",
                prerequisite_concept_ids=[],
            ),
            "C_D": ConceptNode(
                concept_id="C_D",
                name="Conservation of Momentum",
                definition="Momentum conservation derived from Second and Third laws.",
                prerequisite_concept_ids=["C_B"],
            ),
        }
    )


@pytest.fixture
def service(repo: InMemoryMasteryRepository, sample_kg: KnowledgeGraph) -> PersonalizationService:
    dep_provider = ConceptDependencyProvider.from_knowledge_graph(sample_kg)
    return PersonalizationService(mastery_repo=repo, dependency_provider=dep_provider)


def test_01_new_source_unassessed_selects_first_eligible_concept(
    service: PersonalizationService, sample_kg: KnowledgeGraph
):
    """Test 1: New learner with no records selects first eligible unassessed concept in curriculum order."""
    roadmap = service.get_roadmap(
        user_id="user_1",
        source_id="SRC_PHYSICS",
        knowledge_graph=sample_kg,
    )

    assert roadmap.user_id == "user_1"
    assert roadmap.source_id == "SRC_PHYSICS"
    assert roadmap.completed is False
    assert roadmap.mastered_concepts == []
    # C_A and C_C have no prerequisites, C_B and C_D are blocked
    assert roadmap.unassessed_concepts == ["C_A", "C_C"]
    assert roadmap.blocked_concepts == ["C_B", "C_D"]

    # Next action must be C_A (first in grounded curriculum order)
    action = roadmap.next_action
    assert action.concept_id == "C_A"
    assert action.action_type == LearningActionType.ASSESS
    assert action.reason_code == ReasonCode.NEXT_GROUNDED_CONCEPT
    assert action.dependency_status == "SATISFIED"
    assert roadmap.current_concept == "C_A"


def test_02_weak_concept_selects_remediate(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 2: A concept in WEAK state prioritizes REMEDIATE action."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a = sm.record_assessment_attempt(rec_a, "ATT_01", is_correct=False)
    assert rec_a.mastery_state == MasteryState.WEAK
    repo.save(rec_a)

    action = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert action.concept_id == "C_A"
    assert action.action_type == LearningActionType.REMEDIATE
    assert action.reason_code == ReasonCode.WEAK_CONCEPT_REQUIRES_REMEDIATION
    assert action.mastery_state == MasteryState.WEAK


def test_03_reassessing_concept_selects_reassess(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 3: A concept in REASSESSING state prioritizes REASSESS action over weak and unassessed concepts."""
    # C_A is in REASSESSING
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a = sm.record_assessment_attempt(rec_a, "ATT_01", is_correct=False)
    rec_a = sm.assign_remediation(rec_a)
    rec_a = sm.confirm_remediation(rec_a)
    assert rec_a.mastery_state == MasteryState.REASSESSING
    repo.save(rec_a)

    # C_C is also WEAK
    rec_c = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_C")
    rec_c = sm.record_assessment_attempt(rec_c, "ATT_02", is_correct=False)
    repo.save(rec_c)

    action = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert action.concept_id == "C_A"
    assert action.action_type == LearningActionType.REASSESS
    assert action.reason_code == ReasonCode.REASSESSMENT_PENDING


def test_04_remediating_concept_selects_active_remediation(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 4: A concept in REMEDIATING state yields active REMEDIATE action."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a = sm.record_assessment_attempt(rec_a, "ATT_01", is_correct=False)
    rec_a = sm.assign_remediation(rec_a)
    assert rec_a.mastery_state == MasteryState.REMEDIATING
    repo.save(rec_a)

    action = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert action.concept_id == "C_A"
    assert action.action_type == LearningActionType.REMEDIATE
    assert action.reason_code == ReasonCode.ACTIVE_REMEDIATION


def test_05_mastered_concept_not_selected(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 5: Mastered concept is moved to mastered_concepts and not chosen for learning."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a = sm.record_assessment_attempt(rec_a, "ATT_01", is_correct=True)
    assert rec_a.mastery_state == MasteryState.MASTERED
    repo.save(rec_a)

    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert "C_A" in roadmap.mastered_concepts
    # C_A is mastered, so C_B (prereq C_A) is now unblocked and eligible!
    assert "C_B" in roadmap.unassessed_concepts
    assert roadmap.next_action.concept_id != "C_A"


def test_06_unsatisfied_dependency_blocks_concept(
    service: PersonalizationService,
    sample_kg: KnowledgeGraph,
):
    """Test 6: Concept C_B depending on C_A is BLOCKED while C_A is unassessed/not mastered."""
    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert "C_B" in roadmap.blocked_concepts
    assert "C_D" in roadmap.blocked_concepts
    assert "C_A" not in roadmap.blocked_concepts


def test_07_mastered_dependency_unblocks_concept(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 7: When prerequisite C_A is MASTERED, dependent C_B dynamically becomes eligible."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a = sm.record_assessment_attempt(rec_a, "ATT_01", is_correct=True)
    repo.save(rec_a)

    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert "C_B" not in roadmap.blocked_concepts
    assert "C_B" in roadmap.unassessed_concepts
    # C_D still depends on C_B (which is not yet mastered), so C_D remains blocked
    assert "C_D" in roadmap.blocked_concepts


def test_08_multiple_weak_concepts_deterministic_prioritization(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
):
    """Test 8: Multiple weak concepts are prioritized deterministically without LLM."""
    # Create 3 concepts: W_PREREQ, W_LOW_SCORE, W_HIGH_SCORE
    kg = KnowledgeGraph(
        concepts={
            "W_HIGH_SCORE": ConceptNode(
                concept_id="W_HIGH_SCORE",
                name="High Score Weak",
                prerequisite_concept_ids=[],
            ),
            "W_LOW_SCORE": ConceptNode(
                concept_id="W_LOW_SCORE",
                name="Low Score Weak",
                prerequisite_concept_ids=[],
            ),
            "W_DEPENDENT": ConceptNode(
                concept_id="W_DEPENDENT",
                name="Dependent Weak",
                prerequisite_concept_ids=["W_LOW_SCORE"],
            ),
        }
    )
    dep_prov = ConceptDependencyProvider.from_knowledge_graph(kg)
    srv = PersonalizationService(mastery_repo=repo, dependency_provider=dep_prov)

    # 1. W_DEPENDENT depends on W_LOW_SCORE. W_LOW_SCORE should come before W_DEPENDENT topologically!
    rec_dep = sm.create_initial_record("user_1", "SRC_TEST", "W_DEPENDENT")
    rec_dep.mastery_state = MasteryState.WEAK
    rec_dep.mastery_score = 10.0
    repo.save(rec_dep)

    rec_low = sm.create_initial_record("user_1", "SRC_TEST", "W_LOW_SCORE")
    rec_low.mastery_state = MasteryState.WEAK
    rec_low.mastery_score = 30.0  # Even though score is 30 > 10, it is prerequisite to W_DEPENDENT!
    repo.save(rec_low)

    action = srv.get_next_action("user_1", "SRC_TEST", knowledge_graph=kg)
    assert action.concept_id == "W_LOW_SCORE"

    # 2. When no prerequisite relationship, lower score comes first
    rec_high = sm.create_initial_record("user_1", "SRC_TEST", "W_HIGH_SCORE")
    rec_high.mastery_state = MasteryState.WEAK
    rec_high.mastery_score = 50.0
    repo.save(rec_high)

    rec_other = sm.create_initial_record("user_1", "SRC_TEST", "W_OTHER")
    # Independent lower score
    kg.concepts["W_OTHER"] = ConceptNode(concept_id="W_OTHER", name="Other", prerequisite_concept_ids=[])
    rec_other.mastery_state = MasteryState.WEAK
    rec_other.mastery_score = 20.0
    repo.save(rec_other)

    # Re-evaluate with W_OTHER (score 20) vs W_HIGH_SCORE (score 50)
    kg_independent = KnowledgeGraph(
        concepts={
            "W_HIGH_SCORE": kg.concepts["W_HIGH_SCORE"],
            "W_OTHER": kg.concepts["W_OTHER"],
        }
    )
    srv_indep = PersonalizationService(mastery_repo=repo, dependency_provider=ConceptDependencyProvider.from_knowledge_graph(kg_independent))
    action_indep = srv_indep.get_next_action("user_1", "SRC_TEST", knowledge_graph=kg_independent)
    assert action_indep.concept_id == "W_OTHER"  # 20.0 < 50.0


def test_09_needs_support_concept_no_automatic_remediation(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 9: Concept in NEEDS_SUPPORT triggers MANUAL_SUPPORT_REQUIRED when all concepts need support."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.NEEDS_SUPPORT
    rec_a.remediation_attempt_count = 3
    repo.save(rec_a)

    rec_c = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_C")
    rec_c.mastery_state = MasteryState.MASTERED
    repo.save(rec_c)

    # C_B and C_D depend on C_A (which is in NEEDS_SUPPORT, not MASTERED)
    # Therefore C_B and C_D are BLOCKED.
    # The only remaining unmastered concept is C_A (NEEDS_SUPPORT).
    action = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert action.concept_id == "C_A"
    assert action.action_type == LearningActionType.NEEDS_SUPPORT
    assert action.reason_code == ReasonCode.MANUAL_SUPPORT_REQUIRED


def test_10_needs_support_prerequisite_keeps_dependent_blocked(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 10: Downstream dependent C_B remains BLOCKED when prerequisite C_A is in NEEDS_SUPPORT."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.NEEDS_SUPPORT
    rec_a.remediation_attempt_count = 3
    repo.save(rec_a)

    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert "C_A" in roadmap.needs_support_concepts
    assert "C_B" in roadmap.blocked_concepts
    assert "C_D" in roadmap.blocked_concepts


def test_11_independent_concept_learnable_despite_other_needs_support(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 11: Independent concept C_C remains actionable/learnable even though C_A is in NEEDS_SUPPORT."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.NEEDS_SUPPORT
    rec_a.remediation_attempt_count = 3
    repo.save(rec_a)

    # C_C is unassessed and has no prerequisites
    action = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    # C_C should be selected for learning/assessment! It is NOT blocked by C_A!
    assert action.concept_id == "C_C"
    assert action.action_type == LearningActionType.ASSESS
    assert action.reason_code == ReasonCode.NEXT_GROUNDED_CONCEPT


def test_12_all_concepts_mastered_yields_complete(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 12: When all grounded concepts are MASTERED, roadmap is completed and action is COMPLETE."""
    for cid in ["C_A", "C_B", "C_C", "C_D"]:
        rec = sm.create_initial_record("user_1", "SRC_PHYSICS", cid)
        rec.mastery_state = MasteryState.MASTERED
        rec.mastery_score = 100.0
        rec.attempt_count = 2
        rec.correct_count = 2
        repo.save(rec)

    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert roadmap.completed is True
    assert set(roadmap.mastered_concepts) == {"C_A", "C_B", "C_C", "C_D"}
    assert roadmap.weak_concepts == []
    assert roadmap.blocked_concepts == []
    assert roadmap.needs_support_concepts == []
    assert roadmap.next_action.action_type == LearningActionType.COMPLETE
    assert roadmap.next_action.concept_id is None
    assert roadmap.next_action.reason_code == ReasonCode.ALL_CONCEPTS_MASTERED


def test_13_unknown_synthetic_concept_rejected(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 13: Mastery records for synthetic or non-existent concepts are excluded from the roadmap."""
    # Legitimate concept
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.MASTERED
    repo.save(rec_a)

    # Synthetic concept not in sample_kg
    rec_fake = sm.create_initial_record("user_1", "SRC_PHYSICS", "SYNTHETIC_CONCEPT_999")
    rec_fake.mastery_state = MasteryState.WEAK
    repo.save(rec_fake)

    roadmap = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)

    # SYNTHETIC_CONCEPT_999 must NOT appear anywhere in the roadmap
    all_roadmap_cids = (
        roadmap.mastered_concepts
        + roadmap.weak_concepts
        + roadmap.unassessed_concepts
        + roadmap.blocked_concepts
        + roadmap.needs_support_concepts
    )
    assert "SYNTHETIC_CONCEPT_999" not in all_roadmap_cids
    assert roadmap.next_action.concept_id != "SYNTHETIC_CONCEPT_999"


def test_14_cross_user_isolation(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 14: User A's mastery records do not leak into User B's roadmap."""
    # User A mastered C_A
    rec_a = sm.create_initial_record("user_A", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.MASTERED
    repo.save(rec_a)

    # User B has no records
    roadmap_b = service.get_roadmap("user_B", "SRC_PHYSICS", knowledge_graph=sample_kg)

    assert "C_A" not in roadmap_b.mastered_concepts
    assert "C_A" in roadmap_b.unassessed_concepts
    assert "C_B" in roadmap_b.blocked_concepts  # B is still blocked for User B!


def test_15_cross_source_isolation(
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
):
    """Test 15: Concepts from Source 1 are isolated from Source 2."""
    kg_src1 = KnowledgeGraph(concepts={"C_S1": ConceptNode(concept_id="C_S1", name="S1")})
    kg_src2 = KnowledgeGraph(concepts={"C_S2": ConceptNode(concept_id="C_S2", name="S2")})

    srv1 = PersonalizationService(repo, ConceptDependencyProvider.from_knowledge_graph(kg_src1))
    srv2 = PersonalizationService(repo, ConceptDependencyProvider.from_knowledge_graph(kg_src2))

    rec1 = sm.create_initial_record("user_1", "SRC_1", "C_S1")
    rec1.mastery_state = MasteryState.MASTERED
    repo.save(rec1)

    roadmap_2 = srv2.get_roadmap("user_1", "SRC_2", knowledge_graph=kg_src2)

    assert "C_S1" not in roadmap_2.mastered_concepts
    assert "C_S1" not in roadmap_2.unassessed_concepts
    assert roadmap_2.unassessed_concepts == ["C_S2"]


def test_16_pure_read_side_effect_free(
    service: PersonalizationService,
    repo: InMemoryMasteryRepository,
    sm: MasteryStateMachine,
    sample_kg: KnowledgeGraph,
):
    """Test 16: Calling get_roadmap and get_next_action multiple times is pure and side-effect free."""
    rec_a = sm.create_initial_record("user_1", "SRC_PHYSICS", "C_A")
    rec_a.mastery_state = MasteryState.WEAK
    rec_a.attempt_count = 1
    rec_a.incorrect_count = 1
    repo.save(rec_a)

    # Initial state snapshot
    initial_records = repo.list_by_user_source("user_1", "SRC_PHYSICS")
    assert len(initial_records) == 1
    initial_rec = initial_records[0].model_dump()

    # Call get_roadmap and get_next_action multiple times
    for _ in range(5):
        rm = service.get_roadmap("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)
        act = service.get_next_action("user_1", "SRC_PHYSICS", knowledge_graph=sample_kg)
        assert rm.next_action.concept_id == "C_A"
        assert act.concept_id == "C_A"

    # Post-check: zero mutation
    post_records = repo.list_by_user_source("user_1", "SRC_PHYSICS")
    assert len(post_records) == 1
    assert post_records[0].model_dump() == initial_rec
