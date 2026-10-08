"""The deployed CAS column must not alter the public session contract."""
from types import SimpleNamespace
from uuid import UUID
import pytest
from app.services.learning_session import LearningSessionRepository
from app.services.repositories.knowledge_repository import KnowledgeError

OWNER = UUID("00000000-0000-4000-8000-000000000001")

def row():
    return {"user_id": str(OWNER), "source_id": "source", "source_version": 1,
            "session_id": "00000000-0000-4000-8000-000000000002",
            "topic_id": "topic", "subtopic_id": None, "selected_concept_ids": ["concept"],
            "state": "ACTIVE", "created_at": "2026-10-08T00:00:00Z",
            "updated_at": "2026-10-08T00:00:00Z", "last_active_at": "2026-10-08T00:00:00Z"}

def repository():
    return LearningSessionRepository(SimpleNamespace(user=SimpleNamespace(user_id=OWNER)))

def test_internal_revision_is_not_public_scope():
    legacy = repository()._decode(row())
    deployed = repository()._decode({**row(), "mastery_revision": 2})
    assert legacy == deployed
    assert "mastery_revision" not in deployed.model_dump()

@pytest.mark.parametrize("revision", [-1, True, "1", None, 1.5])
def test_invalid_revision_fails_closed(revision):
    with pytest.raises(KnowledgeError, match="INVALID_PROVIDER_RESPONSE"):
        repository()._decode({**row(), "mastery_revision": revision})

def test_other_unexpected_storage_fields_still_fail_closed():
    with pytest.raises(KnowledgeError, match="INVALID_PROVIDER_RESPONSE"):
        repository()._decode({**row(), "mastery_revision": 0, "unexpected": "value"})
