"""Step 4 — Question Validation Gateway.

Ensures every question is structurally perfect before dispatching to the student.
"""

from .schemas import Question


def validate_question(question: Question) -> tuple[bool, str]:
    """Validate a question's structure. Returns (is_valid, error_message)."""

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
