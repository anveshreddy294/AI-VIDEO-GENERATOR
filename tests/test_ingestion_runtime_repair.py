"""Modality isolation, bounded reasoning, and safe asynchronous failure regressions."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pymupdf as fitz
import pytest

from app.core.model_manager import ModelManager
from app.services import dispatcher, extractor, structurer
from app.services.schemas import ContentUnit
from app.services.pipeline_tracker import PipelineJob


def unit(text: str, content_id: str = 'CU_test') -> ContentUnit:
    return ContentUnit(source_id='SRC_test', asset_id='AST_test', content_id=content_id,
                       modality='txt', text=text)


def test_txt_never_calls_vision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'lesson.TXT'
    path.write_text('Photosynthesis converts sunlight into chemical energy.', encoding='utf-8')
    forbidden = MagicMock(side_effect=AssertionError('TXT called vision'))
    monkeypatch.setattr(dispatcher, 'describe_image_file', forbidden)
    monkeypatch.setattr(dispatcher, 'describe_image_file_async', forbidden)
    monkeypatch.setattr(extractor, 'describe_image', forbidden)
    assert dispatcher.dispatch(path, 'SRC_test', 'AST_test').modality == 'txt'
    assert asyncio.run(dispatcher.dispatch_async(path, 'SRC_test', 'AST_test')).units
    forbidden.assert_not_called()


@pytest.mark.parametrize('extension', ['png', 'jpg', 'jpeg'])
def test_images_require_vision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str) -> None:
    path = tmp_path / ('image.' + extension)
    path.write_bytes((Path(__file__).parent/'fixtures/multimodal/printed.png').read_bytes())
    from app.services import visual_evidence
    def visual(*args, **kwargs):
        return ContentUnit(source_id=kwargs['source_id'],asset_id=kwargs['asset_id'],modality='image',text='Observed chlorophyll diagram.',visual_description='Observed chlorophyll diagram.')
    vision=MagicMock(side_effect=visual)
    monkeypatch.setattr(visual_evidence,'visual_content_unit',vision)
    assert dispatcher.dispatch(path, 'SRC_test', 'AST_test').units[0].visual_description
    vision.assert_called_once()


@pytest.mark.parametrize('scanned_kind', ['raster', 'vector'])
def test_pdf_only_visual_pages_invoke_vision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scanned_kind: str) -> None:
    path = tmp_path / 'mixed.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), 'Photosynthesis converts sunlight into chemical energy.')
        page = doc.new_page()
        if scanned_kind == 'vector':
            page.draw_rect(fitz.Rect(60, 60, 200, 200))
        else:
            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
            image.clear_with(255)
            page.insert_image(fitz.Rect(60, 60, 200, 200), stream=image.tobytes('png'))
        doc.save(path)
    from app.services import visual_evidence
    def visual(*args, **kwargs):
        return ContentUnit(source_id=kwargs['source_id'],asset_id=kwargs['asset_id'],modality='pdf',text='A rectangular visual diagram.',page_number=kwargs['page_number'],extraction_method='vision_ollama')
    vision=MagicMock(side_effect=visual)
    monkeypatch.setattr(visual_evidence,'visual_content_unit',vision)
    result = extractor.extract_from_pdf(path, 'SRC_test', 'AST_test')
    assert [row.extraction_method for row in result] == ['pymupdf_block', 'vision_ollama']
    assert vision.call_count == 1
    assert 'p.2' in vision.call_args.kwargs['source']


def test_text_pdf_does_not_call_vision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'text.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), 'Chlorophyll absorbs light in plant leaves.')
        doc.save(path)
    forbidden = MagicMock(side_effect=AssertionError('Text PDF called vision'))
    monkeypatch.setattr(extractor, 'describe_image', forbidden)
    assert extractor.extract_from_pdf(path, 'SRC_test', 'AST_test')
    forbidden.assert_not_called()


def test_batches_preserve_every_character_and_bound_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    text = ('Photosynthesis converts light into chemical energy. ' * 650) + 'IMPORTANT_TAIL'
    source = unit(text)
    batches = structurer._structure_batches([source])
    assert ''.join(part.text for batch in batches for part in batch) == text
    assert all(sum(len(part.text) + len(part.content_id) + 40 for part in batch)
               <= structurer.STRUCTURE_BATCH_CHARS for batch in batches)
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps({'concepts': [{'name': 'Photosynthesis', 'definition': 'Invented fact',
                           'source_content_ids': ['CU_test'], 'prerequisite_concept_ids': []}]})

    monkeypatch.setattr(structurer, '_generate_with_llm', generate)
    enriched, graph, _ = structurer.process_structure_and_concepts([source])
    assert len(prompts) == len(batches)
    assert enriched[0].text == text
    assert len(graph.concepts) == 1
    assert all(node.definition in text and 'Invented fact' not in node.definition for node in graph.concepts.values())
    assert 'IMPORTANT_TAIL' in prompts[-1]


def test_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    generate = MagicMock(side_effect=TimeoutError('secret raw prompt'))
    monkeypatch.setattr(structurer, '_generate_with_llm', generate)
    with pytest.raises(TimeoutError, match='Structuring timed out'):
        structurer.process_structure_and_concepts([unit('Photosynthesis converts light energy.')])
    assert generate.call_count == 1


def test_ungrounded_output_creates_no_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(structurer, '_generate_with_llm', lambda _: json.dumps({'concepts': [
        {'name': 'Quantum gravity', 'definition': 'Invented', 'source_content_ids': ['CU_test']}]}))
    with pytest.raises(RuntimeError, match='Knowledge extraction failed'):
        structurer.process_structure_and_concepts([unit('Photosynthesis converts sunlight into energy.')])


def test_reasoning_request_has_no_vision_and_bounded_output(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = ModelManager()
    manager.active_provider = 'ollama'
    manager.fallback_chain = [{'model': 'gemma3:4b', 'provider': 'ollama'}]
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"response":"{}","done":true}'
    request = MagicMock(return_value=response)
    monkeypatch.setattr('app.core.model_manager.urllib.request.urlopen', request)
    manager.generate_with_fallback('evidence', reasoning_only=True, max_output_tokens=768)
    payload = json.loads(request.call_args.args[0].data)
    assert payload['model'] == 'llama3.2:3b'
    assert 'images' not in payload
    assert payload['options']['num_predict'] == 768


def test_explicit_job_lifecycle_preserves_legacy_status() -> None:
    job = PipelineJob(job_id='JOB_test', job_type='source_ingestion')
    assert job.state == 'QUEUED'
    job.status = 'running'
    assert job.state == 'RUNNING'
    job.status, job.is_finished = 'completed', True
    assert job.state == 'SUCCEEDED'
    job.status = 'failed'
    assert job.model_dump()['state'] == 'FAILED'
