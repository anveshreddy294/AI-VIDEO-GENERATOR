"""Tests for SEC-001: Path Traversal Protection in Video Artifact Store."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.video.artifact_store import (
    InvalidIdentifierError,
    get_video_dir,
    validate_path_component,
)
from app.core.config import settings


@pytest.mark.parametrize(
    "valid_id",
    [
        "normal-id",
        "student_123",
        "source-abc",
        "STU_001",
        "SRC.v1",
        "a",
        "12345",
        "A-Z_0-9.valid",
    ],
)
def test_valid_identifiers_accepted(valid_id):
    assert validate_path_component(valid_id) == valid_id


@pytest.mark.parametrize(
    "malicious_id,reason",
    [
        ("../../escape", "parent traversal with slash"),
        ("../escape", "relative parent with slash"),
        ("..", "double dot relative"),
        (".", "single dot relative"),
        ("foo/bar", "forward slash"),
        ("foo\\bar", "backward slash"),
        ("/tmp/test", "absolute unix path"),
        ("C:\\temp", "windows drive prefix"),
        ("C:/temp", "windows drive prefix slash"),
        ("", "empty string"),
        ("   ", "whitespace only"),
        ("a" * 129, "very long identifier exceeding 128 chars"),
        ("student\x00null", "null byte injection"),
        ("student\nnewline", "newline injection"),
        ("student\rreturn", "carriage return injection"),
        ("student;rm -rf", "command separator"),
        ("student|pipe", "pipe character"),
        ("student$var", "dollar variable"),
        ("student`cmd`", "backticks"),
        ("étudiant", "non-ascii unicode characters"),
        ("student\tspace", "tab character"),
    ],
)
def test_malicious_identifiers_rejected(malicious_id, reason):
    with pytest.raises(InvalidIdentifierError):
        validate_path_component(malicious_id)


def test_get_video_dir_containment_and_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "video_output_dir", tmp_path / "videos")

    # Valid path creates correct nested directory
    vdir = get_video_dir("student_1", "source_1", "concept_1")
    assert vdir.exists()
    assert vdir.is_dir()
    assert vdir.relative_to(tmp_path / "videos") == Path("student_1/source_1/concept_1")

    # Malicious student_id escaping base dir is blocked
    with pytest.raises(InvalidIdentifierError):
        get_video_dir("../../escape", "source_1", "concept_1")

    # Malicious concept_id escaping base dir is blocked
    with pytest.raises(InvalidIdentifierError):
        get_video_dir("student_1", "source_1", "../../escape")

    # Malicious source_id is blocked
    with pytest.raises(InvalidIdentifierError):
        get_video_dir("student_1", "/tmp/escape", "concept_1")

    # Confirm no escaped directories were created
    assert not (tmp_path / "escape").exists()


def test_api_video_generate_rejects_traversal():
    client = TestClient(app)
    response = client.post(
        "/video/generate",
        json={
            "student_id": "../../evil_student",
            "source_id": "SRC_DEFAULT",
            "concept_id": "CONCEPT_001",
            "mock_mode": True,
        },
    )
    assert response.status_code == 400
    assert "Invalid student_id" in response.json().get("detail", "") or "traversal" in response.json().get("detail", "").lower()


def test_api_video_status_rejects_traversal():
    client = TestClient(app)
    response = client.get("/video/status/..%2F..%2Fevil")
    assert response.status_code in (400, 404)
