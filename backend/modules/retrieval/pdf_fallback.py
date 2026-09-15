"""Deterministic lexical resilience; physical PDF pages, never a semantic index."""
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

STOP = set("a an the of and or in on to is are for with explain what how does please me about".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP]


@lru_cache(maxsize=8)
def _pages(path, mtime, size):
    import fitz
    with fitz.open(path) as doc:
        return tuple(page.get_text() for page in doc)


def retrieve_pdf_sections(topic, pdf: Path, document_id, resolution_source):
    if not pdf.is_file():
        return []
    stat = pdf.stat()
    pages = _pages(str(pdf), stat.st_mtime_ns, stat.st_size)
    query = set(tokens(topic))
    if not query:
        return []
    counts = [Counter(tokens(text)) for text in pages]
    idf = {w: math.log(1 + len(pages) / (1 + sum(w in c for c in counts))) for w in query}
    ranked = []
    for i, (text, count) in enumerate(zip(pages, counts)):
        hits = query.intersection(count)
        if len(hits) < min(2, len(query)) or len(text.strip()) < 100:
            continue
        score = sum(idf[w] * (1 + math.log(count[w])) for w in hits) / (1 + len(tokens(text)) / 1000)
        ranked.append((score, i, text))
    sections = []
    for score, i, text in sorted(ranked, key=lambda item: (-item[0], item[1]))[:3]:
        # Center the bounded excerpt on an actual query hit.
        match = re.search(r"\b(?:" + "|".join(re.escape(w) for w in sorted(query)) + r")\b", text, re.I)
        start = max(0, (match.start() if match else 0) - 250)
        excerpt = text[start:start + 3000]
        sections.append({
            "title": f"{document_id} — PDF page {i + 1}",
            "breadcrumb": document_id, "node_id": f"pdf-page-{i + 1}",
            "start_page": i + 1, "end_page": i + 1, "page_numbers": [i + 1],
            "summary": "", "keywords": sorted(query.intersection(counts[i])),
            "semantic_tags": [], "learning_objectives": [], "visualizable_elements": [],
            "prerequisites": [], "score": score, "content": excerpt,
            "artifacts_dir": None, "document_id": document_id,
            "resolution_source": resolution_source, "retrieval_mode": "pdf_lexical",
            "page_numbering": "physical_pdf",
        })
    return sections
