"""No-network diagnostics: preserve fixed vision categories independently of verification."""
import base64
import io
import logging
import pytest
from PIL import Image
from pydantic import ValidationError
from app.core.config import settings
from app.core.processing_errors import ProcessingError
from app.services.vision import VisionExtractionFailed, SAFE_VISION_ERROR_CODES
from app.services.visual_verifier import VisualVerificationFailed, VisualVerificationResult
from app.services.ingestion.failures import ingestion_stage, SourceIngestionFailed, SourceFailure
from app.services.pipeline_tracker import PipelineJob
from app.services.visual_router import private_image_transport
from app.services import visual_evidence

SECRET = 'Bearer private-token provider body prompt C:/private/image.jpg'

@pytest.mark.parametrize('code', sorted(SAFE_VISION_ERROR_CODES))
def test_vision_category_survives_serialized_job_without_provider_data(code: str) -> None:
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage('EXTRACTION'):
            raise VisionExtractionFailed(SECRET,code)
    failure=caught.value.failure
    assert failure.stage=='EXTRACTION' and failure.code=='VISION_EXTRACTION_FAILED'
    assert failure.vision_error_code==code and failure.reason_code is None
    job=PipelineJob(job_id='JOB_test',job_type='source_ingestion',status='failed',is_finished=True,failure=failure,error=failure.message)
    encoded=job.model_dump_json()
    assert code in encoded and SECRET not in encoded and 'private-token' not in encoded


def test_arbitrary_vision_code_cannot_cross_public_boundary():
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage('EXTRACTION'): raise VisionExtractionFailed(SECRET,SECRET)
    assert caught.value.failure.vision_error_code=='VISION_PROVIDER_FAILED'
    assert SECRET not in caught.value.failure.model_dump_json()
    with pytest.raises(ValidationError):
        SourceFailure(stage='EXTRACTION',code='VISION_EXTRACTION_FAILED',vision_error_code=SECRET,retryable=True,message='safe')

@pytest.mark.parametrize('status',['UNCERTAIN','REJECTED'])
def test_verification_keeps_its_independent_stage(status: str):
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage('EXTRACTION'): raise VisualVerificationFailed(VisualVerificationResult(status=status))
    assert caught.value.failure.stage=='VERIFICATION'
    assert caught.value.failure.vision_error_code is None
    assert caught.value.failure.retryable is False


def test_processing_error_behavior_is_unchanged():
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage('EXTRACTION'): raise ProcessingError('MODEL_TIMEOUT',SECRET)
    assert caught.value.failure.reason_code=='MODEL_TIMEOUT'
    assert caught.value.failure.vision_error_code is None
    assert SECRET not in caught.value.failure.model_dump_json()


def jpeg() -> bytes:
    image=Image.new('RGB',(24,24),'white');buffer=io.BytesIO();image.save(buffer,format='JPEG');return buffer.getvalue()


def test_valid_jpeg_decode_and_private_transport_reach_provider(monkeypatch: pytest.MonkeyPatch,caplog: pytest.LogCaptureFixture):
    raw=jpeg();transport=private_image_transport(raw)
    assert transport.startswith('data:image/jpeg;base64,')
    with Image.open(io.BytesIO(base64.b64decode(transport.split(',',1)[1]))) as image: image.verify()
    calls=[]
    monkeypatch.setattr(settings,'vision_provider','ollama')
    def provider(image_bytes: bytes, *, source: str):
        calls.append(image_bytes);raise VisionExtractionFailed(SECRET,'VISION_INVALID_RESPONSE')
    monkeypatch.setattr(visual_evidence,'extract_vision_ollama',provider)
    with caplog.at_level(logging.WARNING),pytest.raises(VisionExtractionFailed):
        visual_evidence.visual_content_unit(raw,source_id='SRC_owned',asset_id='AST_owned',source='private.jpg')
    assert calls==[raw]
    record=next(record for record in caplog.records if record.message=='VISUAL_EXTRACTION_FAILED')
    assert record.source_id=='SRC_owned' and record.stage=='EXTRACTION'
    assert record.vision_error_code=='VISION_INVALID_RESPONSE' and record.provider_route=='ollama'
    assert record.exc_info is None and SECRET not in caplog.text and 'private.jpg' not in caplog.text


def test_verification_is_not_logged_as_extraction(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING),pytest.raises(VisualVerificationFailed):
        with visual_evidence._extraction_diagnostics('SRC_owned'):
            raise VisualVerificationFailed(VisualVerificationResult(status='UNCERTAIN'))
    assert not any(record.message=='VISUAL_EXTRACTION_FAILED' for record in caplog.records)
