"""Unit tests for document resolution in pageindex_retriever."""

import pytest
import json
from modules.retrieval import pageindex_retriever as retriever

from modules.retrieval.pageindex_retriever import (
    DocumentResolutionError,
    _match_folder,
    _resolve_doc_folder,
    clear_artifacts_cache,
    indexed_folders,
    resolve_document,
    retrieve_curriculum,
    validate_document_request,
)


@pytest.fixture(autouse=True)
def _fresh_registry(monkeypatch, tmp_path):
    # These unit tests exercise indexed retrieval, independent of local artifacts.
    monkeypatch.setattr(retriever, "_RESULTS_ROOT", tmp_path)
    for name, title in [("physics.pdf", "Work Energy and Power Gravitation"),
                        ("Chemistry.pdf", "Atomic Structure Chemical Bonding")]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "structure.json").write_text(json.dumps({
            "doc_name": name, "structure": [{"node_id": "1", "title": title,
            "start_index": 1, "end_index": 1, "start_page": 1, "end_page": 1,
            "summary": title, "keywords": title.lower().split()}]}))
        (folder / "extracted_pages.json").write_text(json.dumps([
            {"page": 1, "text": title + " textbook fixture."}]))
    monkeypatch.delenv("PAGEINDEX_ACTIVE_DOC", raising=False)
    clear_artifacts_cache()
    yield
    clear_artifacts_cache()


def test_indexed_folders_contains_physics_and_chemistry():
    folders = indexed_folders()
    assert "physics.pdf" in folders
    assert "Chemistry.pdf" in folders


def test_match_folder_exact_and_case_insensitive():
    assert _match_folder("physics.pdf") == "physics.pdf"
    assert _match_folder("Physics.pdf") == "physics.pdf"


def test_match_folder_stale_kerala_alias():
    stale = (
        "SCERT Kerala State Syllabus 10th Standard Physics "
        "Textbooks English Medium Part 1.pdf"
    )
    assert _match_folder(stale) == "physics.pdf"


def test_match_folder_unknown_returns_none():
    assert _match_folder("nonexistent.pdf") is None
    assert _match_folder("ilovepdf_merged.pdf") is None


def test_resolve_physics_subject_without_document_id():
    folder, source = _resolve_doc_folder(None, subject="Physics")
    assert folder == "physics.pdf"
    assert source == "subject"


def test_resolve_stale_document_id_with_physics_subject():
    stale = (
        "SCERT Kerala State Syllabus 10th Standard Physics "
        "Textbooks English Medium Part 1.pdf"
    )
    folder, source = _resolve_doc_folder(stale, subject="Physics")
    assert folder == "physics.pdf"
    assert source == "request"


def test_resolve_unknown_document_id_with_subject_falls_back_to_subject():
    folder, source = _resolve_doc_folder("deleted_book.pdf", subject="Physics")
    assert folder == "physics.pdf"
    assert source == "subject"


def test_resolve_unknown_document_id_without_subject_raises():
    with pytest.raises(DocumentResolutionError, match="did not match any indexed folder"):
        _resolve_doc_folder("deleted_book.pdf", subject=None)


def test_resolve_chemistry_document_id_with_physics_subject_overrides():
    folder, source = _resolve_doc_folder("Chemistry.pdf", subject="Physics")
    assert folder == "physics.pdf"
    assert source == "subject_override"


def test_retrieve_physics_topic_from_physics_book():
    result = retrieve_curriculum("work energy and power", subject="Physics")
    assert result["document_id"] == "physics.pdf"
    assert result["sections"]
    assert "Work" in result["sections"][0]["title"] or "Energy" in result["sections"][0]["title"]


def test_retrieve_physics_topic_not_chemistry_when_subject_set():
    result = retrieve_curriculum(
        "gravitation",
        document_id="Chemistry.pdf",
        subject="Physics",
    )
    assert result["document_id"] == "physics.pdf"
    assert result["resolution_source"] == "subject_override"


def test_validate_document_request_flags_stale_without_subject():
    check = validate_document_request("deleted_book.pdf", None)
    assert check["valid"] is False
    assert check["llm_only"] is True
    assert "error" in check


def test_validate_document_request_stale_with_subject_resolves():
    check = validate_document_request("deleted_book.pdf", "Physics")
    assert check["valid"] is True
    assert check["would_resolve_via"] == "subject"
    assert check["would_resolve_to"] == "physics.pdf"


def test_env_var_is_ignored(monkeypatch):
    monkeypatch.setenv("PAGEINDEX_ACTIVE_DOC", "Chemistry.pdf")
    clear_artifacts_cache()
    folder, source = _resolve_doc_folder(None, subject="Physics")
    assert folder == "physics.pdf"
    assert source == "subject"


def test_resolve_document_llm_only_on_unindexed_subject():
    resolution = resolve_document(None, subject="Biology")
    assert resolution.llm_only is True
    assert resolution.folder is None
    assert resolution.source == "llm_only"
    assert resolution.reason


def test_resolve_document_physics_not_llm_only():
    resolution = resolve_document(None, subject="Physics")
    assert resolution.llm_only is False
    assert resolution.folder == "physics.pdf"
    assert resolution.source == "subject"


def test_retrieve_curriculum_reuses_resolution_without_re_resolving():
    resolution = resolve_document(None, subject="Physics")
    result = retrieve_curriculum("gravitation", resolution=resolution)
    assert result["document_id"] == "physics.pdf"
    assert result["llm_only"] is False


def test_retrieve_curriculum_llm_only_resolution():
    resolution = resolve_document(None, subject="Biology")
    result = retrieve_curriculum("cells", resolution=resolution)
    assert result["llm_only"] is True
    assert result["sections"] == []
    assert result["context_text"] == ""
