import asyncio
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from modules.learning.schemas import LearningSessionKnowledge
from modules.learning.knowledge import build_topic, enrich
from modules.ingestion.service import ingest, MAX_UPLOAD_BYTES
from modules.rag.store import KnowledgeStore
from modules.learning.assessment import generate, submit, public_assessment
from modules.roadmap.service import gaps, roadmap
from modules.learning.tutor import answer_session
from modules.llm.provider import ProviderError, ProviderClient

router = APIRouter()


class SessionRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    subject: str | None = None
    document_id: str | None = None
    input_mode: Literal["topic", "pdf", "txt", "image"] = "topic"
    text: str | None = Field(default=None, max_length=200000)
    allow_generated: bool = True
    learner_profile: dict = Field(default_factory=dict)


def invoke(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError:
        raise HTTPException(404, "Learning record not found") from None
    except ProviderError as exc:
        raise HTTPException(503, {"message": str(exc), "kind": exc.kind, "retryable": exc.retryable}) from None
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid or insufficient educational content for this operation") from None


@router.post("/api/learning/sessions")
def create_session(req: SessionRequest):
    store = KnowledgeStore()
    if req.input_mode == "topic":
        knowledge, warnings = invoke(build_topic, req.topic, req.subject, req.document_id,
                                     req.allow_generated, store)
    else:
        knowledge = LearningSessionKnowledge(topic=req.topic, subject=req.subject, input_mode=req.input_mode)
        warnings = []
        if req.text:
            material, source, chunks = invoke(ingest, req.text.encode(), "notes.txt", "text/plain", knowledge.session_id)
            knowledge.materials.append(material)
            knowledge.sources.append(source)
            knowledge.source_chunks.extend(chunks)
            enrich(knowledge)
    knowledge.learner_profile = req.learner_profile
    store.save(knowledge)
    return {"session_id": knowledge.session_id, "knowledge": knowledge.model_dump(), "warnings": warnings}


@router.get("/api/learning/{session_id}")
def get_session(session_id: str):
    return invoke(KnowledgeStore().load, session_id).model_dump()


@router.post("/api/materials/upload")
async def upload(file: UploadFile = File(...), session_id: str | None = Form(default=None)):
    store = KnowledgeStore()
    knowledge = invoke(store.load, session_id) if session_id else LearningSessionKnowledge(
        topic=file.filename or "Uploaded material", input_mode="pdf")
    if knowledge.status not in ("knowledge_ready", "failed"):
        raise HTTPException(409, "Start a new session to change material after lesson generation")
    payload = bytearray()
    while block := await file.read(65536):
        payload.extend(block)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Upload exceeds configured size limit")
    result = await asyncio.to_thread(invoke, ingest, bytes(payload), file.filename or "",
                                    file.content_type or "", knowledge.session_id)
    material, source, chunks = result
    knowledge.input_mode = material["input_type"]
    knowledge.materials.append(material)
    knowledge.sources.append(source)
    knowledge.source_chunks.extend(chunks)
    if material.get("extraction"):
        knowledge.equations.extend(material["extraction"]["equations"])
    store.save(enrich(knowledge))
    material["detected_concepts"] = material["detected_concepts"] or [c.name for c in knowledge.concepts]
    store.put("material", material["material_id"], knowledge.session_id, material)
    return material


class AssessmentRequest(BaseModel):
    session_id: str
    target_concept_id: str | None = None


class SubmitRequest(BaseModel):
    answers: dict[str, str] = Field(max_length=30)


@router.post("/api/assessment/generate")
def assessment_generate(req: AssessmentRequest):
    return public_assessment(invoke(generate, req.session_id, req.target_concept_id))


@router.get("/api/assessment/{assessment_id}")
def assessment_get(assessment_id: str):
    return public_assessment(invoke(KnowledgeStore().get, "assessment", assessment_id))


@router.post("/api/assessment/{assessment_id}/submit")
def assessment_submit(assessment_id: str, req: SubmitRequest):
    result = invoke(submit, assessment_id, req.answers)
    result["roadmap"] = invoke(roadmap, result["session_id"])
    return result


@router.get("/api/learning/{session_id}/gaps")
def learning_gaps(session_id: str):
    return invoke(gaps, session_id)


@router.get("/api/roadmap/{session_id}")
def roadmap_get(session_id: str):
    store = KnowledgeStore()
    try:
        return store.get("roadmap", session_id)
    except KeyError:
        return invoke(roadmap, session_id, store)


@router.post("/api/roadmap/{session_id}/regenerate")
def roadmap_regenerate(session_id: str):
    return invoke(roadmap, session_id)


class RelearnRequest(BaseModel):
    concept_id: str
    mode: Literal["simple_explanation", "real_world_analogy", "worked_example", "mini_retest", "targeted_visual"]


@router.post("/api/learning/{session_id}/relearn")
def relearn(session_id: str, req: RelearnRequest):
    store = KnowledgeStore()
    knowledge = invoke(store.load, session_id)
    concept = next((c for c in knowledge.concepts if c.concept_id == req.concept_id), None)
    if not concept:
        raise HTTPException(404, "Concept not found in this session")
    if not any(m["concept_id"] == req.concept_id for m in store.list("mastery", session_id)):
        raise HTTPException(409, "Assess this concept before targeted relearning")
    if req.mode == "mini_retest":
        return {"assessment": public_assessment(invoke(generate, session_id, req.concept_id, store))}
    if req.mode == "targeted_visual":
        return {"pipeline_request": {"session_id": session_id, "topic": concept.name,
                "subject": knowledge.subject or "General", "target_concept_id": req.concept_id,
                "remediation_mode": True}}
    question = f"Use a {req.mode.replace('_', ' ')} to teach {concept.name}: {concept.description}"
    return invoke(answer_session, session_id, question, store=store)


@router.get("/api/learning/{session_id}/provenance")
def provenance(session_id: str):
    return invoke(KnowledgeStore().get, "provenance", session_id)


@router.post("/api/providers/health")
def provider_health():
    client = ProviderClient()
    try:
        client.gemini([{"role": "user", "content": "Reply OK."}], max_tokens=64, timeout=20)
        return {"status": "verified", "provider": "gemini", "model": client.model}
    except ProviderError as exc:
        return {"status": "not_verified", "provider": exc.provider, "model": client.model,
                "failure": exc.kind, "retryable": exc.retryable}
