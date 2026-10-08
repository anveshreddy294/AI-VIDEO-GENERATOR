"""HTTP-to-terminal acceptance with explicit offline provider/Data API/vector doubles.

These prove pipeline contracts, not real-model accuracy or live database behavior.
"""
from __future__ import annotations
import io
import json
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from pydantic import JsonValue
from app.main import app
from app.api import pipeline, source_jobs, sources
from app.core.config import settings
from app.services import visual_evidence, independent_visual_verifier, structurer
from app.services.pipeline_tracker import JobManager
from app.services.visual_contracts import VisionExtractionData
from app.services.visual_verifier import VisualEvidenceVerifier, VerificationCheck, VisualSourceContext, VisualVerificationResult, combine_checks
from app.services.schemas import RichChunk
from app.services.repositories.knowledge_repository import KnowledgeRepository
from app.services.retrieval import RetrievalService, RetrievalRequest, Candidate, EmbeddingSpace
from app.db import vector_store
from tests.test_source_supabase import context, Context
from tests.test_canonical_retrieval import IndexDouble, TEXT
from tests.visual_fixture_oracle import REAL_SOURCE_CHECKS

pytestmark = pytest.mark.usefixtures("supabase_storage_mode")
CLASSES = ("txt", "outline", "printed", "low_resolution", "diagram", "dense_diagram", "flowchart", "multi_panel", "app_chrome", "webp", "mismatch", "handwriting")


def fixture_content(kind: str) -> tuple[str, str]:
    return ("Physics notes", "Force equals mass times acceleration") if kind == "handwriting" else ("Osmosis", TEXT)


def material(kind: str) -> tuple[str, bytes, str]:
    if kind == "handwriting":
        return "handwriting.png", (Path(__file__).parent / "fixtures/multimodal/handwriting.png").read_bytes(), "image/png"
    if kind in ("txt", "outline"):
        text = ("# Osmosis\n## Water movement\n" if kind == "outline" else "") + TEXT
        return kind+".txt", text.encode(), "text/plain"
    size = (320,453) if kind == "low_resolution" else (1536,1024) if kind == "dense_diagram" else (720,1800) if kind in ("multi_panel", "app_chrome") else (800,600)
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for top in range(40, size[1]-60, 150 if kind == "dense_diagram" else 400):
        draw.text((20,top), "Osmosis", fill="black")
        draw.text((20,top+25), TEXT, fill="black")
        if kind in ("diagram", "dense_diagram", "flowchart"):
            draw.rectangle((10,top-10,size[0]-10,top+65),outline="blue")
    if kind == "flowchart":
        draw.rectangle((40,140,300,210),outline="blue")
        draw.text((60,165),"Osmosis",fill="black")
        draw.line((170,105,170,140),fill="blue",width=3)
        draw.polygon([(164,132),(176,132),(170,140)],fill="blue")
    if kind == "multi_panel":
        draw.rectangle((0,0,719,1799),fill="black")
        for i in range(3):
            top=160+i*408
            draw.rectangle((0,top,719,top+407),fill=(159,159,159))
            draw.text((20,top+30),"Osmosis",fill="black")
            draw.text((20,top+55),TEXT,fill="black")
            draw.rectangle((0,top+388,719,top+407),fill=(9,76,119))
    if kind == "app_chrome":
        draw.rectangle((0,0,719,100),fill="black")
        draw.text((20,125),"Osmosis",fill="black")
        draw.text((20,150),TEXT,fill="black")
        draw.rectangle((0,1650,719,1799),fill="black")
    encoding = "WEBP" if kind in ("webp", "mismatch") else "PNG"
    output = io.BytesIO(); image.save(output, format=encoding)
    suffix = "webp" if kind == "webp" else "png"
    return kind+"."+suffix, output.getvalue(), "image/"+suffix


class ReviewDouble:
    """Only the literals drawn by this synthetic fixture can receive approval."""
    def __init__(self, allowed: tuple[str,str]) -> None:
        self.allowed = allowed

    def verify(self, image: bytes, unresolved_claims: tuple[VerificationCheck,...], extraction: VisionExtractionData,
               provenance: VisualSourceContext | None) -> VisualVerificationResult:
        return combine_checks([c.model_copy(update={"status":"VERIFIED" if c.claim in self.allowed else "REJECTED",
            "reason":"INDEPENDENT_VISUAL_SUPPORTED", "visible_support":c.claim}) for c in unresolved_claims], "INDEPENDENT_REVIEW_REQUIRED")


@pytest.mark.parametrize("kind", CLASSES)
def test_http_to_canonical_retrieval(kind: str, context: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    remote, repo, _ = context
    manager = JobManager()
    monkeypatch.setattr(pipeline,"job_manager",manager); monkeypatch.setattr(source_jobs,"job_manager",manager)
    monkeypatch.setattr(sources,"get_runtime",lambda:repo.runtime)
    monkeypatch.setattr(sources,"get_current_user",lambda token,runtime:repo.user)
    monkeypatch.setattr(VisualEvidenceVerifier,"_source_checks",REAL_SOURCE_CHECKS)
    monkeypatch.setattr(settings,"vision_provider","ollama")
    title, statement = fixture_content(kind)
    data = VisionExtractionData(visible_text=[statement],headings=[title],confidence=.9,content_kind="TEXT")
    data._actual_model="fixture-extractor"; data._actual_provider="ollama"
    monkeypatch.setattr(visual_evidence,"extract_vision_ollama",lambda *args,**kwargs:data.model_copy(deep=True))
    monkeypatch.setattr(independent_visual_verifier,"configured_visual_verifier",lambda **kwargs:VisualEvidenceVerifier(ReviewDouble((title,statement))))
    indexed: list[RichChunk] = []
    def index(chunks: list[RichChunk]) -> int:
        assert remote.versions[0]["knowledge_state"] == "READY"
        assert remote.sources[0]["status"] != "READY"
        indexed.extend(chunks); return len(chunks)
    monkeypatch.setattr(vector_store,"upsert_chunks",index)
    def proposal(prompt: str) -> str:
        rows=json.loads(prompt.split("SOURCE_DATA=",1)[1].split("\nREPAIR:",1)[0])
        anchor=next(r for r in rows if statement in r["text"])
        evidence=[{"anchor_id":anchor["anchor_id"]}]
        return json.dumps({"topics":[{"key":"t","title":title,"evidence":evidence}],
            "subtopics":[{"key":"s","topic_key":"t","title":title,"evidence":evidence}],
            "concepts":[{"key":"c","subtopic_key":"s","name":title,"definition":statement,"evidence":evidence}],"prerequisites":[]})
    monkeypatch.setattr(structurer,"generate_educational_proposal",proposal)
    client=TestClient(app); headers={"Authorization":"Bearer test-token"}
    uploaded=client.post("/pipeline/upload-and-assess",headers=headers,files={"file":material(kind)})
    assert uploaded.status_code==200, uploaded.text
    job=client.get("/pipeline/jobs/"+uploaded.json()["job_id"],headers=headers).json()
    assert job["state"]=="SUCCEEDED", job.get("failure")
    assert job["source_lifecycle"]=="READY"
    result=job["result"]
    assert result["status"]==result["knowledge_state"]=="READY"
    assert remote.sources[0]["status"]==remote.versions[0]["knowledge_state"]=="READY"
    assert all(remote.knowledge[key] for key in ("topics","subtopics","concepts"))
    assert indexed and all(c["name"]==title for c in remote.knowledge["concepts"])
    knowledge=KnowledgeRepository(repo.user,repo._token,repo.runtime)
    candidates=[Candidate(point_id=vector_store._point_id(c),score=.9,payload={**vector_store._payload(c),**EmbeddingSpace().model_dump()}) for c in indexed]
    bundle=RetrievalService(IndexDouble(candidates)).retrieve(knowledge,RetrievalRequest(source_id=result["source_id"],source_version=result["version"],query=title))
    assert bundle.outcome=="READY" and bundle.items
    assert any(statement in item.excerpt for item in bundle.items)
    if kind in ("webp","mismatch"):
        assert remote.sources[0]["mime_type"]=="image/webp"
        assert remote.versions[0]["provenance"]["file_truth"]["actual_format"]=="WEBP"
        assert remote.sources[0]["filename"]==material(kind)[0]


@pytest.mark.parametrize("kind,code",[("corrupt","CORRUPT_IMAGE"),("unsupported","FILE_TYPE_MISMATCH"),("oversized","IMAGE_TOO_LARGE"),("empty","EMPTY_FILE"),("blank","EMPTY_CONTENT")])
def test_negative_admission_has_no_job_or_canonical_writes(kind: str,code: str,context: Context,monkeypatch: pytest.MonkeyPatch) -> None:
    remote,repo,_=context
    manager=JobManager();monkeypatch.setattr(pipeline,"job_manager",manager);monkeypatch.setattr(source_jobs,"job_manager",manager)
    monkeypatch.setattr(sources,"get_runtime",lambda:repo.runtime);monkeypatch.setattr(sources,"get_current_user",lambda token,runtime:repo.user)
    payload={"corrupt":b"not an image","unsupported":b"%PDF invalid","oversized":b"x"*(8*1024*1024+1),"empty":b""}.get(kind)
    if payload is None:
        output=io.BytesIO();Image.new("RGB",(64,64),"white").save(output,format="PNG");payload=output.getvalue()
    response=TestClient(app).post("/pipeline/upload-and-assess",headers={"Authorization":"Bearer test-token"},files={"file":("input.png",payload,"image/png")})
    assert response.status_code==422 and response.json()["detail"]["code"]==code
    assert not remote.sources and not remote.versions and not remote.units and not manager._jobs
