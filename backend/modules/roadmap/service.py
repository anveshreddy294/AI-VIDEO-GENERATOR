from modules.learning.schemas import uid, now
from modules.rag.store import KnowledgeStore


def gaps(session_id, store=None):
    store = store or KnowledgeStore()
    store.load(session_id)
    items = store.list("mastery", session_id)
    return {"concept_mastery": items, "knowledge_gaps": [m for m in items if m["status"] == "knowledge_gap"],
            "assessed": bool(items)}


def roadmap(session_id, store=None):
    store = store or KnowledgeStore()
    knowledge = store.load(session_id)
    mastery = store.list("mastery", session_id)
    if not mastery:
        raise ValueError("Complete an assessment before requesting a roadmap")
    concepts = {c.concept_id: c for c in knowledge.concepts}
    by_id = {m["concept_id"]: m for m in mastery}
    ordered, visited = [], set()
    def visit(cid):
        if cid in visited or cid not in concepts:
            return
        visited.add(cid)
        for prerequisite in concepts[cid].prerequisites:
            visit(prerequisite)
        ordered.append(cid)
    for m in sorted(mastery, key=lambda item: item["score"]):
        visit(m["concept_id"])
    items = []
    for cid in ordered:
        concept, result = concepts[cid], by_id.get(cid)
        score = result["score"] if result else None
        action = "simple_explanation" if score is None or score < 60 else "practice_mcq" if score < 80 else "next_topic"
        count = len(result["evidence_question_ids"]) if result else 0
        reason = (f"You scored {score}% on {count} question(s) linked to this concept."
                  if result else "This concept is an unassessed prerequisite.")
        profile = knowledge.learner_profile
        if profile.get("exam_target"):
            reason += " Practice supports your stated exam target: " + str(profile["exam_target"])
        items.append({"roadmap_item_id": uid(), "concept_id": cid, "title": concept.name,
            "priority": len(items) + 1, "reason": reason, "action": action,
            "estimated_minutes": 12 if profile.get("pace_preference") == "slow" else 7,
            "status": "recommended" if score is None or score < 80 else "ready_to_advance",
            "prerequisite_ids": concept.prerequisites})
    result = {"session_id": session_id, "items": items, "created_at": now(),
              "basis": "latest assessed concept performance and explicit prerequisites"}
    return store.put("roadmap", session_id, session_id, result)
