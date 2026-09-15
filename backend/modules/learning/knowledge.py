import re
from collections import Counter
from modules.learning.schemas import Concept, LearningSessionKnowledge
from modules.learning.sources import BundledCurriculumSource, TrustedTopicSource, GeneratedLessonSource
from modules.rag.store import KnowledgeStore

STOP = set("the and that this with from have which when their there into they then will does are for not".split())


def enrich(knowledge):
    """Conservative extractive concepts/facts; source text is never executed."""
    seen, facts, concepts = set(), [], []
    for chunk in knowledge.source_chunks:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", chunk.text):
            sentence = sentence.strip()
            words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", sentence) if w.lower() not in STOP]
            if len(sentence) < 40 or len(sentence) > 700 or not words or sentence in seen:
                continue
            seen.add(sentence)
            name = " ".join(w for w, _ in Counter(words).most_common(2)).title()
            concept = Concept(name=name, description=sentence, source_ids=[chunk.source_id])
            concepts.append(concept)
            facts.append({"text": sentence, "source_ids": [chunk.source_id],
                          "chunk_ids": [chunk.chunk_id], "concept_ids": [concept.concept_id],
                          "source_type": chunk.source_type})
            if len(facts) >= 20:
                break
        if len(facts) >= 20:
            break
    knowledge.concepts = concepts
    knowledge.key_facts = facts
    knowledge.definitions = [f["text"] for f in facts if re.search(r"\bis\b|defined", f["text"])][:6]
    knowledge.learning_objectives = [f"Explain {c.name.lower()} using the supplied evidence." for c in concepts[:6]]
    knowledge.lesson_summary = " ".join(f["text"] for f in facts[:3])
    return knowledge


def build_topic(topic, subject=None, document_id=None, allow_generated=True, store=None):
    store = store or KnowledgeStore()
    knowledge = LearningSessionKnowledge(topic=topic, subject=subject)
    warnings = []
    try:
        # Explicit textbook selection takes precedence; arbitrary topics use public evidence.
        if subject or document_id:
            sources, chunks = BundledCurriculumSource(subject, document_id).obtain(topic)
        else:
            raise ValueError("No curriculum selected")
    except (ValueError, OSError):
        try:
            sources, chunks = TrustedTopicSource(store).obtain(topic)
        except Exception:
            if not allow_generated:
                raise ValueError("No external evidence available; generated fallback is disabled")
            sources, chunks = GeneratedLessonSource().obtain(topic)
            warnings.append("AI-generated lesson knowledge; not externally grounded.")
    knowledge.sources, knowledge.source_chunks = sources, chunks
    store.save(enrich(knowledge))
    return knowledge, warnings
