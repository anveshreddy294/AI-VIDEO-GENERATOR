import json
import re
import time
import PyPDF2

try:
    from .utils import get_number_of_pages, remove_fields, structure_to_list, count_tokens
except ImportError:
    from utils import get_number_of_pages, remove_fields, structure_to_list, count_tokens


def count_nodes(structure):
    """Recursively count nodes in a tree (dict nodes or list of roots)."""
    if structure is None:
        return 0
    if isinstance(structure, dict):
        n = 1
        for child in structure.get("nodes", []) or []:
            n += count_nodes(child)
        return n
    if isinstance(structure, list):
        return sum(count_nodes(item) for item in structure)
    return 0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_pages(pages: str) -> list[int]:
    """Parse a pages string like '5-7', '3,8', or '12' into a sorted list of ints."""
    result = []
    for part in pages.split(','):
        part = part.strip()
        if '-' in part:
            start, end = int(part.split('-', 1)[0].strip()), int(part.split('-', 1)[1].strip())
            if start > end:
                raise ValueError(f"Invalid range '{part}': start must be <= end")
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def _count_pages(doc_info: dict) -> int:
    """Return total page count for a PDF document."""
    if doc_info.get('page_count'):
        return doc_info['page_count']
    if doc_info.get('pages'):
        return len(doc_info['pages'])
    return get_number_of_pages(doc_info['path'])


def _get_pdf_page_content(doc_info: dict, page_nums: list[int]) -> list[dict]:
    """Extract text for specific PDF pages (1-indexed). Prefer cached pages, fallback to PDF."""
    cached_pages = doc_info.get('pages')
    if cached_pages:
        page_map = {p['page']: p['content'] for p in cached_pages}
        return [
            {'page': p, 'content': page_map[p]}
            for p in page_nums if p in page_map
        ]
    path = doc_info['path']
    with open(path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        total = len(pdf_reader.pages)
        valid_pages = [p for p in page_nums if 1 <= p <= total]
        return [
            {'page': p, 'content': pdf_reader.pages[p - 1].extract_text() or ''}
            for p in valid_pages
        ]


def _get_md_page_content(doc_info: dict, page_nums: list[int]) -> list[dict]:
    """
    For Markdown documents, 'pages' are line numbers.
    Find nodes whose line_num falls within [min(page_nums), max(page_nums)] and return their text.
    """
    min_line, max_line = min(page_nums), max(page_nums)
    results = []
    seen = set()

    def _traverse(nodes):
        for node in nodes:
            ln = node.get('line_num')
            if ln and min_line <= ln <= max_line and ln not in seen:
                seen.add(ln)
                results.append({'page': ln, 'content': node.get('text', '')})
            if node.get('nodes'):
                _traverse(node['nodes'])

    _traverse(doc_info.get('structure', []))
    results.sort(key=lambda x: x['page'])
    return results


# ── Tool functions ────────────────────────────────────────────────────────────

def get_document(documents: dict, doc_id: str) -> str:
    """Return JSON with document metadata: doc_id, doc_name, doc_description, type, status, page_count (PDF) or line_count (Markdown)."""
    doc_info = documents.get(doc_id)
    if not doc_info:
        return json.dumps({'error': f'Document {doc_id} not found'})
    result = {
        'doc_id': doc_id,
        'doc_name': doc_info.get('doc_name', ''),
        'doc_description': doc_info.get('doc_description', ''),
        'type': doc_info.get('type', ''),
        'status': 'completed',
    }
    if doc_info.get('type') == 'pdf':
        result['page_count'] = _count_pages(doc_info)
    else:
        result['line_count'] = doc_info.get('line_count', 0)
    return json.dumps(result)


def get_document_structure(documents: dict, doc_id: str) -> str:
    """Return tree structure JSON with text fields removed (saves tokens)."""
    doc_info = documents.get(doc_id)
    if not doc_info:
        return json.dumps({'error': f'Document {doc_id} not found'})
    structure = doc_info.get('structure', [])
    structure_no_text = remove_fields(structure, fields=['text'])
    print(f"[retrieve] get_document_structure doc_id={doc_id!r} node_count={count_nodes(structure_no_text)}")
    return json.dumps(structure_no_text, ensure_ascii=False)


def get_page_content(documents: dict, doc_id: str, pages: str) -> str:
    """
    Retrieve page content for a document.

    pages format: '5-7', '3,8', or '12'
    For PDF: pages are physical page numbers (1-indexed).
    For Markdown: pages are line numbers corresponding to node headers.

    Returns JSON list of {'page': int, 'content': str}.
    """
    doc_info = documents.get(doc_id)
    if not doc_info:
        return json.dumps({'error': f'Document {doc_id} not found'})

    print(f"[retrieve] get_page_content doc_id={doc_id!r} pages={pages!r} doc_type={doc_info.get('type')!r}")

    try:
        page_nums = _parse_pages(pages)
    except (ValueError, AttributeError) as e:
        return json.dumps({'error': f'Invalid pages format: {pages!r}. Use "5-7", "3,8", or "12". Error: {e}'})

    try:
        if doc_info.get('type') == 'pdf':
            content = _get_pdf_page_content(doc_info, page_nums)
        else:
            content = _get_md_page_content(doc_info, page_nums)
    except Exception as e:
        return json.dumps({'error': f'Failed to read page content: {e}'})

    return json.dumps(content, ensure_ascii=False)


def _normalize_query(q: str) -> set:
    return set(re.findall(r"[a-zA-Z]{3,}", (q or "").lower()))


def _node_search_text(node: dict) -> str:
    parts = [node.get("title", ""), node.get("summary", "")]
    parts.extend(node.get("keywords") or [])
    return " ".join(str(p) for p in parts).lower()


def _heuristic_relevance(query: str, nodes: list) -> float:
    if not nodes:
        return 0.0
    q_tokens = _normalize_query(query)
    if not q_tokens:
        return 0.0
    scores = []
    for node in nodes:
        text_tokens = set(re.findall(r"[a-zA-Z]{3,}", _node_search_text(node)))
        if not text_tokens:
            scores.append(0.0)
            continue
        overlap = len(q_tokens & text_tokens) / max(len(q_tokens), 1)
        scores.append(overlap)
    return sum(scores) / len(scores)


def _retrieve_nodes(structure, query: str, top_k: int = 5) -> list:
    nodes = structure_to_list(structure)
    q = (query or "").lower()
    scored = []
    for node in nodes:
        text = _node_search_text(node)
        q_tokens = _normalize_query(q)
        if not q_tokens:
            score = 0.0
        else:
            text_tokens = set(re.findall(r"[a-zA-Z]{3,}", text))
            score = len(q_tokens & text_tokens) / max(len(q_tokens), 1)
        if q in text:
            score += 0.5
        scored.append((score, node))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for s, n in scored[:top_k] if s > 0] or [n for _, n in scored[:top_k]]


def benchmark_retrieval(documents: dict, doc_id: str, queries: list) -> dict:
    """Lightweight retrieval benchmark: query -> nodes, relevance, latency, context tokens."""
    doc_info = documents.get(doc_id)
    if not doc_info:
        return {"error": f"Document {doc_id} not found", "queries": []}

    structure = doc_info.get("structure", [])
    results = []
    for q in queries:
        if not q:
            continue
        t0 = time.perf_counter()
        nodes = _retrieve_nodes(structure, q, top_k=5)
        latency_ms = (time.perf_counter() - t0) * 1000
        context_tokens = 0
        for n in nodes:
            if n.get("text"):
                context_tokens += count_tokens(n.get("text", ""), None)
            elif doc_info.get("type") == "pdf" and n.get("start_index"):
                pages = doc_info.get("pages") or []
                for p in pages:
                    if n["start_index"] <= p.get("page", 0) <= n.get("end_index", 0):
                        context_tokens += count_tokens(p.get("content", ""), None)
        relevance = _heuristic_relevance(q, nodes)
        results.append({
            "query": q,
            "node_ids": [n.get("node_id") for n in nodes],
            "titles": [n.get("title") for n in nodes],
            "relevance": round(relevance, 4),
            "latency_ms": round(latency_ms, 2),
            "context_tokens": context_tokens,
        })

    avg_rel = sum(r["relevance"] for r in results) / len(results) if results else 0.0
    avg_lat = sum(r["latency_ms"] for r in results) / len(results) if results else 0.0
    return {
        "doc_id": doc_id,
        "query_count": len(results),
        "avg_relevance": round(avg_rel, 4),
        "avg_latency_ms": round(avg_lat, 2),
        "queries": results,
    }
