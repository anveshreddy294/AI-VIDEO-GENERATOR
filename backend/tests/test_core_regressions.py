import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from modules.manim import semantic_compiler as compiler
from modules.retrieval import pageindex_retriever as retrieval


def test_semantic_compile_without_stub(tmp_path, monkeypatch):
    monkeypatch.setitem(compiler.PATHS, "manim", tmp_path)
    monkeypatch.setattr(compiler, "_compile_stub_fallback",
                        Mock(side_effect=AssertionError("Stub must never run")))
    result = compiler.semantic_compile_all(
        [{"scene_id": 1, "concept_template": "work_energy", "title": "Work and Energy"}],
        [{"scene_id": 1, "audio_duration": 12}], allow_fallback=False)
    ast.parse(result[0][1])
    assert "force_arrow" in result[0][1]


def test_strict_compile_propagates_failure(monkeypatch):
    monkeypatch.setattr(compiler, "semantic_compile", Mock(side_effect=RuntimeError("broken")))
    with pytest.raises(RuntimeError, match="broken"):
        compiler.semantic_compile_all([{"scene_id": 1}], [], allow_fallback=False)


def test_strict_unknown_template():
    with pytest.raises(ValueError, match="Unknown semantic template"):
        compiler.semantic_compile_all(
            [{"scene_id": 1, "concept_template": "not_registered"}], [], allow_fallback=False)


def test_strict_renderer_does_not_generate_placeholder(tmp_path, monkeypatch):
    from modules.manim import renderer
    monkeypatch.setattr(renderer, "_media_dir", lambda workspace: tmp_path)
    monkeypatch.setattr(renderer, "_scene_dest", lambda *args: tmp_path / "scene.mp4")
    monkeypatch.setattr(renderer, "_run_manim", lambda *args: None)
    fallback = Mock(side_effect=AssertionError("Fallback must not run"))
    monkeypatch.setattr(renderer, "_render_minimal_fallback", fallback)
    with pytest.raises(RuntimeError, match="Strict semantic render failed"):
        renderer.render(tmp_path / "scene.py", allow_fallback=False)
    assert not (tmp_path / "scene.mp4").exists()


def test_gemini_fallback_uses_configured_model(monkeypatch):
    from modules.llm import nvidia_client
    monkeypatch.setattr(nvidia_client, "GEMINI_MODEL", "configured-test-model")
    from modules.llm import provider
    model = Mock()
    model.models.generate_content.return_value.text = "test response"
    context = Mock()
    context.__enter__ = Mock(return_value=model)
    context.__exit__ = Mock(return_value=False)
    constructor = Mock(return_value=context)
    monkeypatch.setattr(provider.genai, "Client", constructor)
    nvidia_client.NvidiaClient(max_retries=1)._chat_gemini([{"role": "user", "content": "test"}])
    assert model.models.generate_content.call_args.kwargs["model"] == "configured-test-model"


@pytest.mark.parametrize("topic,subject,book", [
    ("work energy power", "Physics", "physics.pdf"),
    ("atomic structure", "Chemistry", "Chemistry.pdf"),
    ("benzene", "Chemistry", "Chemistry.pdf"),
])
def test_real_pdf_fallback(topic, subject, book, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "_RESULTS_ROOT", tmp_path)
    retrieval.clear_artifacts_cache()
    result = retrieval.retrieve_curriculum(topic, subject=subject)
    assert result["retrieval_mode"] == "pdf_lexical"
    assert result["document_id"] == book
    assert result["sections"]
    assert not retrieval.is_document_indexed(book)
    import fitz
    with fitz.open(retrieval._PAGEINDEX_ROOT / "examples/documents" / book) as pdf:
        for section in result["sections"]:
            assert section["content"] in pdf[section["start_page"] - 1].get_text()
    retrieval.clear_artifacts_cache()


def test_insufficient_pdf_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "_RESULTS_ROOT", tmp_path)
    retrieval.clear_artifacts_cache()
    assert not retrieval.retrieve_curriculum("xyzzynonexistent", subject="Physics")["matched"]
    # This bundled Physics volume does not cover electromagnetic induction.
    assert not retrieval.retrieve_curriculum("electromagnetic induction", subject="Physics")["matched"]
    retrieval.clear_artifacts_cache()


def test_chat_grounded_and_provider_failure(monkeypatch):
    import api
    client = TestClient(api.app)
    fake = Mock()
    fake.chat.return_value = "Work transfers energy. [1]"
    monkeypatch.setattr(api, "NvidiaClient", lambda **kwargs: fake)
    response = client.post("/api/chat", json={"message": "work energy", "subject": "Physics"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["pages"]
    assert "TEXTBOOK EVIDENCE" in fake.chat.call_args.args[1][0]["content"]
    fake.chat.side_effect = RuntimeError("quota")
    assert client.post("/api/chat", json={"message": "work energy", "subject": "Physics"}).status_code == 503


def test_chat_refuses_no_evidence_and_fake_sources(monkeypatch):
    import api
    client = TestClient(api.app)
    fake = Mock()
    monkeypatch.setattr(api, "NvidiaClient", lambda **kwargs: fake)
    response = client.post("/api/chat", json={"message": "xyzzynonexistent", "subject": "Physics"})
    assert response.json()["status"] == "insufficient_evidence"
    fake.chat.assert_not_called()
    fake.chat.return_value = "A claim. [999]"
    assert client.post("/api/chat", json={"message": "work energy", "subject": "Physics"}).status_code == 502
