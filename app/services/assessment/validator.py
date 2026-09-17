"""Step 4 — Question Validation Gateway.

Ensures every question is structurally perfect before dispatching to the student.
"""

from .schemas import Question


def validate_question(
    question: Question,
    allowed_source_id: str | None = None,
) -> tuple[bool, str]:
    """Validate a question's structure and provenance integrity. Returns (is_valid, error_message)."""

    # Check stem
    if not question.stem or not question.stem.strip():
        return False, "Empty question stem"

    # Check exactly 4 options
    if len(question.options) != 4:
        return False, f"Expected 4 options, got {len(question.options)}"

    # Check correct_index is valid
    if not (0 <= question.correct_index <= 3):
        return False, f"Invalid correct_index: {question.correct_index}"

    # Check no duplicate option texts
    option_texts = [opt.text.strip().lower() for opt in question.options]
    if len(set(option_texts)) != 4:
        return False, "Duplicate option texts found"

    # Check no empty options
    for i, opt in enumerate(question.options):
        if not opt.text or not opt.text.strip():
            return False, f"Option {i} is empty"

    # Check explanation exists
    if not question.explanation or not question.explanation.strip():
        return False, "Empty explanation"

    # Check all option indices are 0-3
    indices = {opt.index for opt in question.options}
    if indices != {0, 1, 2, 3}:
        return False, f"Option indices must be 0-3, got {indices}"

    # Check source_id integrity
    if not question.source_id or not question.source_id.strip():
        return False, "Missing source_id in question"

    if allowed_source_id and question.source_id != allowed_source_id:
        return False, f"Question source_id '{question.source_id}' does not match session source_id '{allowed_source_id}'"

    # Provenance anchors: must have at least one of chunk_ids or content_ids
    if not question.chunk_ids and not question.content_ids:
        return False, "Question lacks provenance anchors (both chunk_ids and content_ids are empty)"

    # Page range consistency
    if question.page_start is not None and question.page_end is not None:
        if question.page_start < 0 or question.page_end < 0:
            return False, "Negative page numbers are invalid"
        if question.page_start > question.page_end:
            return False, f"Invalid page range: page_start ({question.page_start}) > page_end ({question.page_end})"

    # Timestamp consistency (for video sources)
    if isinstance(question.timestamp_start, (int, float)) and isinstance(question.timestamp_end, (int, float)):
        if question.timestamp_start < 0 or question.timestamp_end < 0:
            return False, "Negative timestamps are invalid"
        if question.timestamp_start > question.timestamp_end:
            return False, f"Invalid timestamp range: timestamp_start ({question.timestamp_start}) > timestamp_end ({question.timestamp_end})"

    return True, "OK"


def validate_grounding(
    question: Question,
    context_text: str,
    min_overlap_words: int = 1,
) -> tuple[bool, str]:
    """Validate that the question vocabulary has factual overlap with the source context.
    Rejects hallucinated questions with zero semantic grounding in source chunks.
    """
    if not context_text or not context_text.strip():
        return True, "OK"

    import re
    STOP_WORDS = {
        "this", "that", "with", "from", "which", "what", "where", "when",
        "about", "according", "statement", "describes", "characterizes",
        "study", "material", "curriculum", "source", "following", "defined",
        "concept", "principle", "based", "learning", "state", "primarily",
    }
    def extract_tokens(text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z]{4,}", text.lower())
        return {w for w in words if w not in STOP_WORDS}

    context_tokens = extract_tokens(context_text)
    if not context_tokens:
        return True, "OK"

    correct_text = (
        question.options[question.correct_index].text
        if 0 <= question.correct_index < len(question.options)
        else ""
    )
    question_tokens = extract_tokens(f"{question.stem} {correct_text} {question.concept_name}")

    overlap = question_tokens & context_tokens
    if len(overlap) < min_overlap_words:
        return False, f"Question vocabulary has insufficient grounding overlap with source context (overlap: {overlap})"

    return True, "OK"


def is_duplicate(
    new_question: Question,
    existing_questions: list[Question],
    similarity_threshold: float = 0.8,
) -> bool:
    """Check if a question is too similar to existing ones.

    Uses simple text overlap (Jaccard similarity on word sets) for efficiency.
    """
    new_words = set(new_question.stem.lower().split())

    for existing in existing_questions:
        existing_words = set(existing.stem.lower().split())

        # Jaccard similarity
        intersection = new_words & existing_words
        union = new_words | existing_words

        if union and len(intersection) / len(union) > similarity_threshold:
            return True

        # Also check if options overlap significantly
        new_opts = {opt.text.lower() for opt in new_question.options}
        exist_opts = {opt.text.lower() for opt in existing.options}
        opt_intersection = new_opts & exist_opts
        if len(opt_intersection) >= 3:
            return True

    return False
