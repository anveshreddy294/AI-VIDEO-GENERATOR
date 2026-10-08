"""Bounded learner input; questions remain data rather than scope instructions."""

from __future__ import annotations
import re
from typing import Annotated
from pydantic import AfterValidator, Field

MAX_QUESTION_CHARS = 4000
MAX_FOLLOWUP_QUESTIONS = 3
_OVERRIDE = re.compile(
    r"(?:ignore|override|disregard)\s+(?:all\s+)?(?:previous|system|developer)\s+(?:instructions|rules|prompt)"
    r"|(?:reveal|print|show)\s+(?:the\s+)?(?:system\s+prompt|api\s+keys?|secrets?)"
    r"|(?:retrieve|access|search|use)\s+(?:another|other|foreign|unrelated|all)\s+(?:user(?:'s)?\s+)?(?:sources?|documents?|accounts?)"
    r"|<(?:system|developer)>|\[INST\]",
    re.IGNORECASE,
)


def validate_question(value: str) -> str:
    """Reject blank/control inputs and explicit instruction or scope overrides."""
    value = value.strip()
    if (
        not value
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
        or _OVERRIDE.search(value)
    ):
        raise ValueError("INVALID_LEARNER_QUESTION")
    return value


LearnerQuestion = Annotated[
    str,
    Field(min_length=1, max_length=MAX_QUESTION_CHARS),
    AfterValidator(validate_question),
]
