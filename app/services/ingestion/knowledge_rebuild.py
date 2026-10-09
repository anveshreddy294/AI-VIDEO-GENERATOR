"""Explicit verified-only knowledge extension; stage vectors before CAS publication."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from uuid import NAMESPACE_URL, uuid5
from pydantic import ValidationError
from ...core.supabase import SupabaseConflict, SupabaseUnavailable, SupabaseResponseError
from ..content_understanding import understand_content, UnderstandingError
from ..educational_chunker import ChunkPolicy, create_educational_chunks
from ..knowledge_models import (
    KnowledgeSnapshot, CanonicalKnowledge, SnapshotTopic, SnapshotSubtopic,
    SnapshotConcept, SnapshotEvidence, SnapshotRelationship, SnapshotCommit,
)
from ..repositories.knowledge_repository import KnowledgeRepository, KnowledgeError, MAX_SNAPSHOT_BYTES
from ..repositories.source_repository import SupabaseSourceRepository
from ..security.content_sanitizer import SanitizedContent
from ..snapshot_validation import snapshot_knowledge

REBUILD_VERSION = "verified-hierarchy-extension-v1"


def extend_snapshot(existing: CanonicalKnowledge, proposed: KnowledgeSnapshot) -> KnowledgeSnapshot:
    """Deduplicate scoped names, preserving every historical node/link verbatim."""
    topics = [SnapshotTopic.model_validate(t.model_dump(include=set(SnapshotTopic.model_fields))) for t in existing.topics]
    subs = [SnapshotSubtopic.model_validate(s.model_dump(include=set(SnapshotSubtopic.model_fields))) for s in existing.subtopics]
    concepts = [SnapshotConcept.model_validate(c.model_dump(include=set(SnapshotConcept.model_fields))) for c in existing.concepts]
    evidence = [SnapshotEvidence.model_validate(e.model_dump(include=set(SnapshotEvidence.model_fields))) for e in existing.evidence]
    relationships = [SnapshotRelationship.model_validate(r.model_dump(include=set(SnapshotRelationship.model_fields))) for r in existing.relationships]
    topic_names = {t.title.casefold().strip():t.topic_id for t in topics}
    sub_names = {(s.topic_id,s.title.casefold().strip()):s.subtopic_id for s in subs}
    concept_names = {(c.subtopic_id,c.name.casefold().strip()):c.concept_id for c in concepts}
    topic_map: dict[str,str] = {}; sub_map: dict[str,str] = {}; concept_map: dict[str,str] = {}
    for t in sorted(proposed.topics,key=lambda x:(x.sequence,x.topic_id)):
        key=t.title.casefold().strip(); identity=topic_names.get(key)
        if identity is None:
            identity=t.topic_id
            if any(old.topic_id==identity for old in topics):
                raise KnowledgeError("CONFLICT")
            topics.append(t.model_copy(update={"sequence":max((old.sequence for old in topics),default=-1)+1}))
            topic_names[key]=identity
        topic_map[t.topic_id]=identity
    for s in sorted(proposed.subtopics,key=lambda x:(x.sequence,x.subtopic_id)):
        parent=topic_map[s.topic_id];key=(parent,s.title.casefold().strip());identity=sub_names.get(key)
        if identity is None:
            identity=s.subtopic_id
            if any(old.subtopic_id==identity for old in subs):
                raise KnowledgeError("CONFLICT")
            sequence=max((old.sequence for old in subs if old.topic_id==parent),default=-1)+1
            subs.append(s.model_copy(update={"topic_id":parent,"sequence":sequence}));sub_names[key]=identity
        sub_map[s.subtopic_id]=identity
    for c in sorted(proposed.concepts,key=lambda x:(x.sequence,x.concept_id)):
        parent=sub_map[c.subtopic_id];key=(parent,c.name.casefold().strip());identity=concept_names.get(key)
        if identity is None:
            identity=c.concept_id
            if any(old.concept_id==identity for old in concepts):
                raise KnowledgeError("CONFLICT")
            sequence=max((old.sequence for old in concepts if old.subtopic_id==parent),default=-1)+1
            concepts.append(c.model_copy(update={"subtopic_id":parent,"sequence":sequence}));concept_names[key]=identity
        concept_map[c.concept_id]=identity
    link_keys={(e.content_id,e.concept_id,e.support_kind) for e in evidence}
    for e in proposed.content_concepts:
        mapped=e.model_copy(update={"concept_id":concept_map[e.concept_id]})
        key=(mapped.content_id,mapped.concept_id,mapped.support_kind)
        if key not in link_keys:
            evidence.append(mapped);link_keys.add(key)
    edge_keys={(r.concept_id,r.related_concept_id,r.relationship_type) for r in relationships}
    for r in proposed.relationships:
        mapped=r.model_copy(update={"concept_id":concept_map[r.concept_id],"related_concept_id":concept_map[r.related_concept_id]})
        key=(mapped.concept_id,mapped.related_concept_id,mapped.relationship_type)
        if mapped.concept_id==mapped.related_concept_id:
            raise KnowledgeError("INVALID_SCOPE")
        if key not in edge_keys:
            relationships.append(mapped);edge_keys.add(key)
    return KnowledgeSnapshot(schema_version=1,topics=topics,subtopics=subs,concepts=concepts,
        content_concepts=evidence,relationships=relationships)


def rebuild_verified_knowledge(repo: SupabaseSourceRepository, source_id: str,
    generate: Callable[[str],str] | None = None) -> dict[str,int | str]:
    """No extraction/re-ingestion. A failed CAS leaves staged vectors non-canonical."""
    from ...db.vector_store import upsert_chunks
    context=KnowledgeRepository(repo.user,repo._token,repo.runtime)
    record=repo.get_source(source_id)
    if record is None:
        raise KnowledgeError("NOT_FOUND")
    scope=context.scope(source_id,record.version)
    current=context.get_complete_knowledge_map(scope)
    if record.status!="READY" or current.readiness.knowledge_state!="READY" or not current.readiness.payload_hash:
        raise KnowledgeError("NOT_READY")
    version=repo.get_source_version(source_id,record.version)
    units=context.list_scoped_content(scope)
    if version is None or not units:
        raise KnowledgeError("NOT_READY")
    if version.knowledge_diagnostics.get("rebuild_policy")==REBUILD_VERSION:
        return {"topics":len(current.topics),"subtopics":len(current.subtopics),"concepts":len(current.concepts),
            "structuring_calls":0,"repair_calls":0,"status":"UNCHANGED"}
    safe={row.content_id:row for row in (SanitizedContent.model_validate(item) for item in version.sanitized_content)}
    for unit in units:
        verification=unit.provenance.get("visual_verification")
        sanitized=safe.get(unit.content_id)
        if unit.provenance.get("visual_schema_version")!="visual-v2" or not isinstance(verification,dict) or verification.get("status")!="VERIFIED" or sanitized is None or not sanitized.retrieval_allowed or sanitized.injection_status=="quarantined" or sanitized.sanitized_text!=unit.content.text or sanitized.source_id!=source_id or sanitized.source_version!=f"v{record.version}":
            raise UnderstandingError("NO_SAFE_CONTENT")
    proposed=understand_content(scope,units,generate)
    merged=extend_snapshot(current,proposed.snapshot)
    data=snapshot_knowledge(scope,units,merged)
    policy=ChunkPolicy.model_validate(version.provenance.get("chunk_policy") or ChunkPolicy().model_dump())
    chunks,_=create_educational_chunks(scope,units,data,policy,version.file_hash,published=False)
    payload=merged.model_dump(mode="json",exclude_none=True)
    serialized=json.dumps(payload,sort_keys=True,separators=(",",":"))
    if len(serialized.encode())>MAX_SNAPSHOT_BYTES:
        raise KnowledgeError("PAYLOAD_TOO_LARGE")
    operation=uuid5(NAMESPACE_URL,f"{scope.user_id}:{source_id}:{record.version}:{REBUILD_VERSION}:{hashlib.sha256(serialized.encode()).hexdigest()}")
    if current.readiness.operation_id==operation:
        return {"topics":len(merged.topics),"subtopics":len(merged.subtopics),"concepts":len(merged.concepts),"chunks":len(chunks),"structuring_calls":proposed.structuring_model_calls,"repair_calls":proposed.repair_model_calls,"status":"UNCHANGED"}
    # The central index adapter stages deterministic points; manifest membership
    # keeps them invisible until the database CAS publishes the new association set.
    if upsert_chunks(chunks)!=len(chunks):
        raise KnowledgeError("PROVIDER_UNAVAILABLE")
    try:
        value=repo.runtime.user_request("POST","/rest/v1/rpc/visualai_rebuild_verified_knowledge",token=repo._token,body={
            "p_source_id":source_id,"p_source_version":record.version,
            "p_expected_hash":current.readiness.payload_hash,"p_operation_id":str(operation),"p_payload":payload})
        committed=SnapshotCommit.model_validate_json(json.dumps(value))
    except SupabaseConflict:
        raise KnowledgeError("CONFLICT") from None
    except SupabaseUnavailable:
        raise KnowledgeError("PROVIDER_UNAVAILABLE") from None
    except (SupabaseResponseError,ValidationError):
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE") from None
    if committed.source_id!=source_id or committed.source_version!=record.version or committed.operation_id!=operation:
        raise KnowledgeError("INVALID_PROVIDER_RESPONSE")
    return {"topics":len(merged.topics),"subtopics":len(merged.subtopics),"concepts":len(merged.concepts),"chunks":len(chunks),"structuring_calls":proposed.structuring_model_calls,"repair_calls":proposed.repair_model_calls,"status":"READY"}
