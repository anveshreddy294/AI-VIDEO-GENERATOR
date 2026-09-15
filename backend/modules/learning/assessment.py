"""Source-extractive questions and deterministic, explainable scoring."""
import hashlib
import re
from modules.learning.schemas import uid, now
from modules.learning.knowledge import STOP
from modules.rag.store import KnowledgeStore


def words(text):
    return list(dict.fromkeys(w.lower() for w in re.findall(r"[A-Za-z]{4,}", text) if w.lower() not in STOP))


def generate(session_id, target_concept_id=None, store=None):
    store = store or KnowledgeStore()
    knowledge = store.load(session_id)
    if knowledge.status != "complete":
        raise ValueError("Assessment unlocks after successful video completion")
    facts = [f for f in knowledge.key_facts if not target_concept_id or target_concept_id in f["concept_ids"]]
    if not facts or (not target_concept_id and len(facts) < 5):
        raise ValueError("Insufficient evidence for a supported assessment; add more educational material")
    chunk_map = {c.chunk_id: c for c in knowledge.source_chunks}
    for fact in facts:
        if not any(cid in chunk_map and fact["text"] in chunk_map[cid].text for cid in fact["chunk_ids"]):
            raise ValueError("Unsupported assessment fact")
    assessment_id = uid()
    vocab = list(dict.fromkeys(w for f in knowledge.key_facts for w in words(f["text"])))
    questions = []
    count = 3 if target_concept_id else 5
    for i in range(count):
        fact = facts[i % len(facts)]
        terms = words(fact["text"])
        if not terms:
            raise ValueError("No assessable content")
        correct = terms[i % len(terms)]
        distractors = [w for w in vocab if w != correct][:3]
        if len(distractors) < 3:
            raise ValueError("Not enough distinct terms for an unambiguous MCQ")
        options = [correct] + distractors
        options.sort(key=lambda x: hashlib.sha256((assessment_id + x + str(i)).encode()).hexdigest())
        question = re.sub(r"\b" + re.escape(correct) + r"\b", "____", fact["text"], count=1, flags=re.I)
        questions.append({"question_id": uid(), "type": "mcq",
            "question": "Complete this statement from the lesson evidence: " + question,
            "options": options, "correct_answer": correct, "rubric": [],
            "explanation": fact["text"], "difficulty": "easy",
            "concept_ids": fact["concept_ids"], "source_ids": fact["source_ids"], "chunk_ids": fact["chunk_ids"]})
    if not target_concept_id:
        fact = facts[0]
        questions.append({"question_id": uid(), "type": "short",
            "question": "Explain this lesson idea in your own words: " + knowledge.concepts[0].name,
            "options": [], "correct_answer": fact["text"], "rubric": words(fact["text"])[:6],
            "explanation": fact["text"], "difficulty": "medium", "concept_ids": fact["concept_ids"],
            "source_ids": fact["source_ids"], "chunk_ids": fact["chunk_ids"]})
    assessment = {"assessment_id": assessment_id, "session_id": session_id, "questions": questions,
        "generation_mode": "deterministic_source_cloze", "created_at": now(),
        "externally_grounded": all(s.externally_grounded for s in knowledge.sources)}
    return store.put("assessment", assessment_id, session_id, assessment)


def public_assessment(assessment):
    return {**assessment, "questions": [{k: v for k, v in q.items()
        if k not in ("correct_answer", "rubric", "explanation")} for q in assessment["questions"]]}


def evaluate_short(answer, rubric):
    present = set(words(answer))
    missing = [word for word in rubric if word not in present]
    coverage = (len(rubric) - len(missing)) / max(len(rubric), 1)
    score = 100 if coverage >= .8 else 50 if coverage >= .4 else 0
    return {"score": score, "feedback": "correct" if score == 100 else "partially_correct" if score else "incorrect",
            "missing_points": missing, "evaluation_mode": "keyword_rubric"}


def mastery_status(score):
    return "mastered" if score >= 80 else "developing" if score >= 60 else "knowledge_gap"


def submit(assessment_id, answers, store=None, evaluator=None):
    store = store or KnowledgeStore()
    assessment = store.get("assessment", assessment_id)
    known = {q["question_id"] for q in assessment["questions"]}
    if set(answers) - known:
        raise ValueError("Unknown question IDs")
    details, concepts = [], {}
    for q in assessment["questions"]:
        answer = str(answers.get(q["question_id"], ""))[:5000]
        if q["type"] == "mcq":
            score = 100 if answer == q["correct_answer"] else 0
            result = {"score": score, "feedback": "correct" if score else "incorrect", "missing_points": []}
        else:
            result = (evaluator or evaluate_short)(answer, q["rubric"])
            if result["score"] not in (0, 50, 100):
                raise ValueError("Invalid rubric evaluator score")
        weight = {"easy": 1, "medium": 1.5, "hard": 2}[q["difficulty"]]
        for concept_id in q["concept_ids"]:
            item = concepts.setdefault(concept_id, {"total": 0, "weight": 0, "evidence_question_ids": []})
            item["total"] += result["score"] * weight
            item["weight"] += weight
            item["evidence_question_ids"].append(q["question_id"])
        details.append({**result, "question_id": q["question_id"], "answer": answer,
                        "correct_answer": q["correct_answer"], "explanation": q["explanation"]})
    concept_scores = [{"concept_id": cid, "score": round(v["total"] / v["weight"]),
        "status": mastery_status(v["total"] / v["weight"]),
        "evidence_question_ids": v["evidence_question_ids"],
        "common_error": "Review the missed evidence statements" if v["total"] / v["weight"] < 80 else "",
        "recommended_action": "targeted_visual_review" if v["total"] / v["weight"] < 60 else "practice_mcq"}
        for cid, v in concepts.items()]
    result = {"result_id": uid(), "assessment_id": assessment_id, "session_id": assessment["session_id"],
        "score": round(sum(d["score"] for d in details) / len(details)), "feedback": details,
        "concept_scores": concept_scores, "created_at": now()}
    store.put("result", result["result_id"], assessment["session_id"], result)
    for item in concept_scores:
        store.put("mastery", assessment["session_id"] + ":" + item["concept_id"], assessment["session_id"], item)
    return result
