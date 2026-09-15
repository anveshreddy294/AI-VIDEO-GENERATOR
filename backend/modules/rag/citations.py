import re

def validate_citations(answer, retrieved):
    ids = set(re.findall(r"\[([a-f0-9]{32})\]", answer))
    bracketed = set(re.findall(r"\[([^\]]+)\]", answer))
    allowed = {c["chunk_id"] for c in retrieved}
    if not ids or not ids.issubset(allowed) or bracketed != ids:
        raise ValueError("Response contains missing or invented citations")
    return ids
