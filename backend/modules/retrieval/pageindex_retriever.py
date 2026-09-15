"""Retrieve curriculum context from PageIndex pipeline artifacts on disk."""

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TOPIC2MANIM_ROOT = Path(__file__).resolve().parents[3]
if str(_TOPIC2MANIM_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOPIC2MANIM_ROOT))

from PageIndex.pageindex.results_loader import DocumentArtifacts
_PAGEINDEX_ROOT = _TOPIC2MANIM_ROOT / "PageIndex"
_RESULTS_ROOT = _PAGEINDEX_ROOT / "results"

_TOP_K = 3
_CONTENT_CHAR_CAP = 3000

logger = logging.getLogger(__name__)

_artifacts_cache: Dict[str, DocumentArtifacts] = {}
_concept_graph_cache: Dict[str, dict] = {}
_registry_cache: Optional[Dict[str, Dict[str, Any]]] = None

_BLACKLISTED_AUTO_FOLDERS = frozenset({
    "ilovepdf_merged.pdf",
})

_SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "Chemistry":    ["chemistry", "chem"],
    "Physics":      ["physics", "phys"],
    "Biology":      ["biology", "bio"],
    "Mathematics":  ["mathematics", "maths", "math"],
}

_CHEMISTRY_TOPIC_TERMS = frozenset({
    "atom", "atomic", "bohr", "rutherford", "thomson", "electron",
    "proton", "neutron", "nucleus", "orbital", "shell", "isotope",
    "isobar", "periodic", "period", "group", "electronegativity",
    "ionic", "covalent", "bond", "bonding", "redox", "oxidation",
    "reduction", "oxidizing", "reducing", "discharge", "cathode",
    "canal", "scattering", "valence", "configuration",
})

_CHEMISTRY_BOOST_TAGS = frozenset({
    "atomic-structure", "nuclear-model", "periodic-table",
    "chemical-bonding", "redox", "electron-configuration",
})


class DocumentResolutionError(RuntimeError):
    """Raised when no valid indexed document can be resolved for the request."""


@dataclass
class DocumentResolution:
    """Result of a single document-resolution pass for one pipeline request."""

    folder: Optional[str]
    source: str
    requested_document_id: Optional[str]
    requested_subject: Optional[str]
    canonical_subject: Optional[str]
    indexed: List[str]
    llm_only: bool = False
    reason: Optional[str] = None


def _normalize(name: str) -> str:
    base = name.lower().removesuffix(".pdf")
    return re.sub(r"[^a-z0-9]+", "", base)


def _basename_from_document_id(document_id: str) -> str:
    clean = document_id.strip().replace("\\", "/")
    if "/" in clean:
        clean = clean.rsplit("/", 1)[-1]
    return clean


# Legacy document_id values that may still appear in sessions or cached UI state.
_KNOWN_STALE_ALIASES: Dict[str, str] = {
    _normalize("SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1.pdf"): "physics.pdf",
    _normalize("SCERT Kerala State Syllabus 10th Standard Physics Textbooks English Medium Part 1"): "physics.pdf",
    _normalize("Physics 10 Part 1.pdf"): "physics.pdf",
    _normalize("NCERT Physics Class 11 Part 1.pdf"): "physics.pdf",
}


def _canonical_subject(subject: Optional[str]) -> Optional[str]:
    if not subject or not subject.strip():
        return None
    raw = subject.strip()
    for canonical in _SUBJECT_KEYWORDS:
        if raw.lower() == canonical.lower():
            return canonical
    return raw


def _guess_subject(name: str) -> str:
    lower = name.lower()
    for subject, keywords in _SUBJECT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return subject
    return "General"


def _indexed_folders() -> List[Path]:
    if not _RESULTS_ROOT.is_dir():
        return []
    return [
        p for p in _RESULTS_ROOT.iterdir()
        if p.is_dir() and (p / "structure.json").is_file()
    ]


def _registry() -> Dict[str, Dict[str, Any]]:
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    entries: Dict[str, Dict[str, Any]] = {}
    for folder_path in _indexed_folders():
        structure_path = folder_path / "structure.json"
        doc_name = folder_path.name
        try:
            with open(structure_path, encoding="utf-8") as f:
                structure = json.load(f)
            doc_name = structure.get("doc_name") or folder_path.name
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read structure.json for %s: %s", folder_path.name, exc)

        entries[folder_path.name] = {
            "folder": folder_path.name,
            "normalized": _normalize(folder_path.name),
            "doc_name": doc_name,
            "doc_name_normalized": _normalize(doc_name),
            "subject": _guess_subject(f"{folder_path.name} {doc_name}"),
            "mtime": structure_path.stat().st_mtime,
        }

    # PDFs remain available without claiming that they have PageIndex artifacts.
    documents = _PAGEINDEX_ROOT / "examples" / "documents"
    for pdf in sorted(documents.glob("*.pdf")):
        if pdf.name in _BLACKLISTED_AUTO_FOLDERS:
            continue
        entries.setdefault(pdf.name, {
            "folder": pdf.name, "normalized": _normalize(pdf.name),
            "doc_name": pdf.name, "doc_name_normalized": _normalize(pdf.name),
            "subject": _guess_subject(pdf.name), "mtime": pdf.stat().st_mtime,
        })
    _registry_cache = entries
    return entries


def _match_folder(document_id: str) -> Optional[str]:
    if not document_id or not document_id.strip():
        return None

    reg = _registry()
    if not reg:
        return None

    doc_id = _basename_from_document_id(document_id)
    by_name = {name: meta for name, meta in reg.items()}

    # Tier 1: exact folder name
    if doc_id in by_name:
        return doc_id
    if not doc_id.endswith(".pdf") and f"{doc_id}.pdf" in by_name:
        return f"{doc_id}.pdf"
    if doc_id.endswith(".pdf") and doc_id[:-4] in by_name:
        return doc_id[:-4]

    needle_norm = _normalize(doc_id)
    if not needle_norm:
        return None

    # Tier 2: known stale alias → current indexed folder
    alias_target = _KNOWN_STALE_ALIASES.get(needle_norm)
    if alias_target and alias_target in by_name:
        logger.info(
            "Resolved stale document_id=%r via alias -> %r",
            document_id,
            alias_target,
        )
        return alias_target

    # Tier 3: normalized exact match on folder or doc_name
    norm_exact = [
        name for name, meta in by_name.items()
        if meta["normalized"] == needle_norm or meta["doc_name_normalized"] == needle_norm
    ]
    if len(norm_exact) == 1:
        return norm_exact[0]
    if len(norm_exact) > 1:
        logger.warning(
            "document_id=%r normalized to multiple folders %s; refusing ambiguous match",
            document_id,
            norm_exact,
        )
        return None

    # Tier 4: strict containment — folder name must be a substantial token in the id
    containment: List[str] = []
    for name, meta in by_name.items():
        folder_norm = meta["normalized"]
        doc_norm = meta["doc_name_normalized"]
        if len(folder_norm) < 4:
            continue
        if folder_norm == needle_norm or doc_norm == needle_norm:
            containment.append(name)
            continue
        if folder_norm in needle_norm and len(folder_norm) >= max(5, len(needle_norm) // 4):
            containment.append(name)
            continue
        if needle_norm in folder_norm and len(needle_norm) >= max(5, len(folder_norm) // 4):
            containment.append(name)

    if len(containment) == 1:
        logger.info(
            "Resolved document_id=%r via containment -> %r",
            document_id,
            containment[0],
        )
        return containment[0]
    if len(containment) > 1:
        logger.warning(
            "document_id=%r matched multiple indexed folders %s; refusing ambiguous match",
            document_id,
            containment,
        )
    return None


def _folder_subject(folder: str) -> str:
    return _registry().get(folder, {}).get("subject", _guess_subject(folder))


def _subject_conflicts(requested: str, resolved_folder: str) -> bool:
    canonical = _canonical_subject(requested)
    if not canonical:
        return False
    resolved = _folder_subject(resolved_folder)
    return resolved not in ("General", canonical)


def indexed_folders() -> List[str]:
    """Return sorted folder names for all currently indexed documents."""
    return sorted(p.name for p in _indexed_folders())


def is_document_indexed(document_id: str) -> bool:
    """Return True when document_id resolves to a currently indexed folder."""
    folder = _match_folder(document_id)
    return bool(folder and (_RESULTS_ROOT / folder / "structure.json").is_file())


def _folders_for_subject(subject: str) -> List[str]:
    canonical = _canonical_subject(subject)
    if not canonical:
        return []

    keywords = _SUBJECT_KEYWORDS.get(canonical, [canonical.lower()])
    reg = _registry()
    candidates = [
        name for name, meta in reg.items()
        if name not in _BLACKLISTED_AUTO_FOLDERS
        and (
            meta["subject"] == canonical
            or any(kw in name.lower() or kw in meta["doc_name"].lower() for kw in keywords)
        )
    ]
    if not candidates:
        return []

    return [max(candidates, key=lambda n: reg[n]["mtime"])]


def _newest_folder(allow_blacklisted: bool = False) -> Optional[str]:
    reg = _registry()
    if not reg:
        return None

    candidates = [
        name for name in reg
        if allow_blacklisted or name not in _BLACKLISTED_AUTO_FOLDERS
    ]
    if not candidates and not allow_blacklisted:
        candidates = list(reg.keys())
    if not candidates:
        return None

    return max(candidates, key=lambda n: reg[n]["mtime"])


def _log_resolution(
    requested_id: Optional[str],
    requested_subject: Optional[str],
    folder: Optional[str],
    source: str,
    indexed: Optional[List[str]] = None,
) -> None:
    reg = _registry()
    resolved_subject = (
        reg.get(folder, {}).get("subject", _guess_subject(folder))
        if folder
        else None
    )
    indexed_list = indexed if indexed is not None else sorted(reg.keys())

    logger.info(
        "[RESOLUTION] requested_subject=%r requested_document_id=%r "
        "resolved_folder=%r resolved_subject=%r resolution_source=%s indexed=%s",
        requested_subject,
        requested_id,
        folder,
        resolved_subject,
        source,
        indexed_list,
    )


def _resolve_doc_folder(
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> Tuple[str, str]:
    """Strict subject-first resolution. Raises DocumentResolutionError on failure."""
    reg = _registry()
    if not reg:
        raise DocumentResolutionError(
            f"No indexed documents found under {_RESULTS_ROOT}. "
            "Run PageIndex indexing before retrieval."
        )

    canonical_subject = _canonical_subject(subject)
    indexed = indexed_folders()

    if canonical_subject:
        subject_matches = _folders_for_subject(canonical_subject)
        if not subject_matches:
            raise DocumentResolutionError(
                f"No indexed document matches subject={canonical_subject!r}. "
                f"Indexed folders: {indexed}. "
                f"Index a {canonical_subject} textbook or pass a valid document_id."
            )
        subject_folder = subject_matches[0]

        if document_id:
            matched = _match_folder(document_id)
            if matched and not _subject_conflicts(canonical_subject, matched):
                return matched, "request"
            if matched and _subject_conflicts(canonical_subject, matched):
                logger.warning(
                    "[RESOLUTION] subject_override document_id=%r -> %r (%s) "
                    "conflicts with requested_subject=%r; using %r",
                    document_id,
                    matched,
                    _folder_subject(matched),
                    canonical_subject,
                    subject_folder,
                )
                return subject_folder, "subject_override"
            logger.warning(
                "[RESOLUTION] stale document_id=%r; using subject=%r -> %r",
                document_id,
                canonical_subject,
                subject_folder,
            )
            return subject_folder, "subject"

        return subject_folder, "subject"

    if document_id:
        matched = _match_folder(document_id)
        if matched:
            return matched, "request"
        raise DocumentResolutionError(
            f"document_id={document_id!r} did not match any indexed folder. "
            f"Indexed folders: {indexed}. "
            "Pass a valid document_id from /api/curriculum/documents or provide subject."
        )

    newest = _newest_folder(allow_blacklisted=False)
    if newest:
        logger.warning(
            "[RESOLUTION] no document_id or subject; defaulting to newest folder %r",
            newest,
        )
        return newest, "newest"

    newest_any = _newest_folder(allow_blacklisted=True)
    if newest_any:
        logger.warning(
            "[RESOLUTION] non-blacklisted folders exhausted; using %r",
            newest_any,
        )
        return newest_any, "newest"

    raise DocumentResolutionError(
        f"Unable to resolve document folder under {_RESULTS_ROOT}."
    )


def resolve_document(
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> DocumentResolution:
    """Resolve the indexed textbook folder once per request."""
    reg = _registry()
    indexed = indexed_folders()
    canonical = _canonical_subject(subject)

    try:
        folder, source = _resolve_doc_folder(document_id, subject)
        _log_resolution(document_id, subject, folder, source, indexed)
        return DocumentResolution(
            folder=folder,
            source=source,
            requested_document_id=document_id,
            requested_subject=subject,
            canonical_subject=canonical,
            indexed=indexed,
            llm_only=False,
        )
    except DocumentResolutionError as exc:
        logger.warning(
            "[RESOLUTION][DEGRADED] requested_subject=%r requested_document_id=%r "
            "reason=%s indexed=%s -> LLM-only mode",
            subject,
            document_id,
            exc,
            indexed,
        )
        return DocumentResolution(
            folder=None,
            source="llm_only",
            requested_document_id=document_id,
            requested_subject=subject,
            canonical_subject=canonical,
            indexed=indexed,
            llm_only=True,
            reason=str(exc),
        )


def validate_document_request(
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """Pre-flight check used by the API before starting the pipeline."""
    resolution = resolve_document(document_id, subject)
    result: Dict[str, Any] = {
        "indexed_folders": resolution.indexed,
        "requested_document_id": document_id,
        "requested_subject": resolution.canonical_subject,
        "valid": not resolution.llm_only,
        "would_resolve_to": resolution.folder,
        "would_resolve_via": resolution.source,
        "llm_only": resolution.llm_only,
    }
    if resolution.llm_only:
        result["error"] = resolution.reason
        result["warning"] = "Grounded video generation requires readable textbook evidence."
    elif resolution.source == "newest":
        result["warning"] = "No document_id or subject provided; using newest indexed folder"
    return result


def _resolve_active_doc() -> str:
    folder, _ = _resolve_doc_folder(None, subject=None)
    return folder


def _resolve_pdf_path(document_id: Optional[str] = None) -> Path:
    folder, _ = _resolve_doc_folder(document_id, subject=None)
    candidate = _PAGEINDEX_ROOT / "examples" / "documents" / folder
    if candidate.is_file():
        return candidate
    return _PAGEINDEX_ROOT / "examples" / "documents" / f"{folder}.pdf"


def _artifacts_for_folder(folder: str, source: str) -> DocumentArtifacts:
    if folder not in _artifacts_cache:
        results_dir = _RESULTS_ROOT / folder
        if not results_dir.is_dir() or not (results_dir / "structure.json").is_file():
            raise FileNotFoundError(
                f"PageIndex results not found at {results_dir}. "
                f"Run: cd PageIndex && PYTHONPATH=. python run_pageindex.py "
                f'--pdf_path "<path/to/doc.pdf>" --model qwen2.5:3b --force-reindex'
            )
        _artifacts_cache[folder] = DocumentArtifacts(results_dir)
        logger.info("Loaded PageIndex artifacts folder=%r source=%s path=%s", folder, source, results_dir)

    artifacts = _artifacts_cache[folder]
    if not artifacts.exists():
        raise FileNotFoundError(
            f"PageIndex results not found at {artifacts.results_dir}. "
            f"Run: cd PageIndex && PYTHONPATH=. python run_pageindex.py "
            f'--pdf_path "<path/to/doc.pdf>" --model qwen2.5:3b --force-reindex'
        )
    return artifacts


def _get_artifacts() -> DocumentArtifacts:
    folder, source = _resolve_doc_folder(None, subject=None)
    return _artifacts_for_folder(folder, source)


def clear_artifacts_cache() -> None:
    global _registry_cache
    _artifacts_cache.clear()
    _concept_graph_cache.clear()
    _registry_cache = None


def list_documents() -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for folder_name, meta in sorted(_registry().items(), key=lambda x: x[0].lower()):
        arts = DocumentArtifacts(_RESULTS_ROOT / folder_name)
        nodes = arts.walk_nodes() if arts.exists() else []
        docs.append({
            "id": folder_name,
            "doc_name": meta["doc_name"],
            "node_count": len(nodes),
            "subject": meta["subject"],
            "indexed": arts.exists(),
            "retrieval_mode": "pageindex" if arts.exists() else "pdf_lexical",
            "blacklisted": folder_name in _BLACKLISTED_AUTO_FOLDERS,
        })
    return docs


def _load_concept_graph(artifacts: DocumentArtifacts) -> dict:
    key = str(artifacts.results_dir)
    if key in _concept_graph_cache:
        return _concept_graph_cache[key]
    data = artifacts.load("concept_graph.json") or {}
    _concept_graph_cache[key] = data
    return data


def _resolve_prerequisites(node_id: str, graph: dict, all_nodes: list) -> List[dict]:
    if not node_id or not graph:
        return []
    id_to_node = {n.get("node_id"): n for n in all_nodes if n.get("node_id")}
    title_map = {n.get("node_id"): n.get("title") for n in graph.get("nodes") or []}
    prereqs: List[dict] = []
    for edge in graph.get("edges") or []:
        if edge.get("to") != node_id or edge.get("relation") != "prerequisite":
            continue
        fid = edge.get("from")
        if not fid:
            continue
        node = id_to_node.get(fid) or {}
        prereqs.append({
            "node_id": fid,
            "title": title_map.get(fid) or node.get("title") or fid,
        })
    return prereqs


def _score_node(node: dict, topic_words: set, document_subject: str = "General") -> float:
    title = (node.get("title") or "").lower()
    summary = (node.get("summary") or "").lower()
    keywords = " ".join(node.get("keywords") or []).lower()
    tags_list = [t.lower() for t in (node.get("semantic_tags") or [])]
    tags_str = " ".join(tags_list)
    vis_elements = [v.lower() for v in (node.get("visualizable_elements") or [])]

    combined = f"{title} {summary} {keywords} {tags_str}"

    def _wb_hit(word: str, text: str) -> bool:
        return bool(re.search(r"\b" + re.escape(word) + r"\b", text))

    hits = sum(1.0 for w in topic_words if _wb_hit(w, combined))

    tag_boost = 0.0
    if document_subject == "Chemistry":
        tag_boost = 2.0 if (
            any(t in _CHEMISTRY_BOOST_TAGS for t in tags_list)
            and bool(topic_words & _CHEMISTRY_TOPIC_TERMS)
        ) else 0.0

    vis_boost = sum(
        0.5 for ve in vis_elements
        if any(_wb_hit(w, ve) for w in topic_words)
    )

    depth_bonus = 0.1 * (node.get("level", 1) - 1)
    summary_bonus = 0.2 if len((node.get("summary") or "")) > 30 else 0.0

    return hits + tag_boost + vis_boost + depth_bonus + summary_bonus


def _breadcrumb(node: dict, all_nodes: list) -> str:
    parent_id = node.get("parent_id")
    parts = [node.get("title", "")]
    visited = {node.get("node_id")}
    while parent_id:
        parent = next((n for n in all_nodes if n.get("node_id") == parent_id), None)
        if not parent or parent.get("node_id") in visited:
            break
        parts.insert(0, parent.get("title", ""))
        visited.add(parent.get("node_id"))
        parent_id = parent.get("parent_id")
    return " > ".join(p for p in parts if p)


def format_sections_for_prompt(sections: List[Dict[str, Any]]) -> str:
    if not sections:
        return ""
    lines = ["MATCHED CURRICULUM SECTIONS WITH VISUAL METADATA:"]
    for sec in sections:
        crumb = sec.get("breadcrumb") or sec.get("title", "")
        start, end = sec.get("start_page"), sec.get("end_page")
        pages = f"pp. {start}–{end}" if start and end else ""
        kw = ", ".join((sec.get("keywords") or [])[:6])
        tags = ", ".join(sec.get("semantic_tags") or [])
        vis = "; ".join(sec.get("visualizable_elements") or [])
        prereqs = sec.get("prerequisites") or []
        prereq_titles = ", ".join(
            p.get("title", "") for p in prereqs if p.get("title")
        )

        lines.append(f"  [{crumb}]{(' (' + pages + ')') if pages else ''}")
        if kw:
            lines.append(f"    Keywords: {kw}")
        if tags:
            lines.append(f"    Tags: {tags}")
        if vis:
            lines.append(f"    Visualizable elements: {vis}  ← use these for template selection")
        if prereq_titles:
            lines.append(f"    Prerequisites: {prereq_titles}")
    return "\n".join(lines)


def format_prerequisites_for_prompt(sections: List[Dict[str, Any]]) -> str:
    if not sections:
        return ""
    seen: set[str] = set()
    ordered: List[str] = []
    for sec in sorted(sections, key=lambda s: int(s.get("start_page") or 0)):
        for prereq in sec.get("prerequisites") or []:
            title = (prereq.get("title") or "").strip()
            if title and title.lower() not in seen:
                seen.add(title.lower())
                ordered.append(title)
    if not ordered:
        return ""
    lines = ["PREREQUISITE LEARNING ORDER (teach these before dependent topics):"]
    for i, title in enumerate(ordered[:12], start=1):
        lines.append(f"  {i}. {title}")
    return "\n".join(lines)


def _build_sections(
    topic: str,
    folder: str,
    source: str,
    artifacts: DocumentArtifacts,
) -> List[Dict[str, Any]]:
    all_nodes = artifacts.walk_nodes()
    graph = _load_concept_graph(artifacts)
    if not all_nodes:
        logger.warning(
            "No nodes in structure.json at %s (document=%s source=%s)",
            artifacts.results_dir,
            folder,
            source,
        )
        return []

    topic_words = set(w for w in topic.lower().split() if len(w) > 2)
    doc_subject = _folder_subject(folder)
    scored = [
        (node, _score_node(node, topic_words, document_subject=doc_subject))
        for node in all_nodes
        if node.get("content_type") != "preface"
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_matches = [(n, s) for n, s in scored[:_TOP_K] if s > 0]
    if not top_matches:
        logger.info(
            "No matching nodes topic=%r document=%s source=%s",
            topic,
            folder,
            source,
        )
        return []

    sections: List[Dict[str, Any]] = []
    for node, score in top_matches:
        start = node.get("start_page") or node.get("start_index")
        end = node.get("end_page") or node.get("end_index")
        page_text = ""
        page_numbers: List[int] = []
        if start and end:
            pages = artifacts.get_pages(int(start), int(end))
            page_numbers = [int(p["page"]) for p in pages if p.get("page")]
            page_text = artifacts.get_page_text(
                int(start), int(end), max_chars=_CONTENT_CHAR_CAP, skip_garbled=True
            )

        node_id = node.get("node_id", "")
        sections.append({
            "title": node.get("title", ""),
            "breadcrumb": _breadcrumb(node, all_nodes),
            "node_id": node_id,
            "start_page": start,
            "end_page": end,
            "page_numbers": page_numbers,
            "summary": node.get("summary", ""),
            "keywords": node.get("keywords", []),
            "semantic_tags": node.get("semantic_tags", []),
            "learning_objectives": node.get("learning_objectives", []),
            "visualizable_elements": node.get("visualizable_elements", []),
            "grade_appropriateness": node.get("grade_appropriateness", ""),
            "prerequisites": _resolve_prerequisites(node_id, graph, all_nodes),
            "score": score,
            "content": page_text,
            "artifacts_dir": str(artifacts.results_dir),
            "document_id": folder,
            "resolution_source": source,
        })

    top = sections[0]
    logger.info(
        "Retrieved %d sections topic=%r document=%s source=%s top=%r breadcrumb=%r pages=%s-%s",
        len(sections),
        topic,
        folder,
        source,
        top.get("title"),
        top.get("breadcrumb"),
        top.get("start_page"),
        top.get("end_page"),
    )
    return sections


def _sections_to_context_text(sections: List[Dict[str, Any]]) -> str:
    parts = []
    for sec in sections:
        crumb = sec["breadcrumb"] or sec["title"]
        start, end = sec.get("start_page"), sec.get("end_page")
        page_ref = f"pages {start}-{end}" if start and end else "pages unknown"
        kw = ", ".join(sec["keywords"][:6]) if sec["keywords"] else ""
        tags = ", ".join(sec.get("semantic_tags") or [])[:80]
        prereq_titles = ", ".join(p.get("title", "") for p in sec.get("prerequisites") or [])
        chunk = f"[{crumb}] ({page_ref})"
        if sec["summary"]:
            chunk += f"\nSummary: {sec['summary']}"
        if kw:
            chunk += f"\nKeywords: {kw}"
        if tags:
            chunk += f"\nTags: {tags}"
        if prereq_titles:
            chunk += f"\nPrerequisites: {prereq_titles}"
        if sec.get("learning_objectives"):
            chunk += f"\nObjectives: {'; '.join(sec['learning_objectives'][:3])}"
        if sec["content"]:
            chunk += f"\nSource text:\n{sec['content']}"
        else:
            chunk += "\n(No readable page text.)"
        parts.append(chunk)
    return "\n\n---\n\n".join(parts)


def retrieve_curriculum_sections(
    topic: str,
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return retrieve_curriculum(topic, document_id=document_id, subject=subject).get("sections", [])


def retrieve_curriculum_context(
    topic: str,
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    return retrieve_curriculum(topic, document_id=document_id, subject=subject).get("context_text", "")


def retrieve_curriculum(
    topic: str,
    document_id: Optional[str] = None,
    subject: Optional[str] = None,
    resolution: Optional[DocumentResolution] = None,
) -> Dict[str, Any]:
    if resolution is None:
        resolution = resolve_document(document_id, subject)

    if resolution.llm_only:
        return {
            "topic": topic,
            "matched": False,
            "sections": [],
            "context_text": "",
            "document_id": None,
            "resolution_source": "llm_only",
            "llm_only": True,
            "resolution_reason": resolution.reason,
        }

    folder = resolution.folder
    source = resolution.source
    mode = "pageindex"
    try:
        artifacts = _artifacts_for_folder(folder, source)
        sections = _build_sections(topic, folder, source, artifacts)
        sections = [s for s in sections if s.get("content", "").strip() and s.get("page_numbers")]
    except (FileNotFoundError, OSError, ValueError):
        sections = []
    if not sections:
        from modules.retrieval.pdf_fallback import retrieve_pdf_sections
        mode = "pdf_lexical"
        pdf = _PAGEINDEX_ROOT / "examples" / "documents" / folder
        if not pdf.is_file():
            pdf = pdf.with_name(folder + ".pdf")
        sections = retrieve_pdf_sections(topic, pdf, folder, source)

    return {
        "topic": topic,
        "matched": bool(sections),
        "retrieval_mode": mode,
        "sections": sections,
        "context_text": _sections_to_context_text(sections) if sections else "",
        "document_id": folder,
        "resolution_source": source,
        "llm_only": False,
    }


try:
    PDF_PATH = _resolve_pdf_path()
    RESULTS_DIR = _RESULTS_ROOT / _resolve_active_doc()
except DocumentResolutionError:
    PDF_PATH = _PAGEINDEX_ROOT / "examples" / "documents"
    RESULTS_DIR = _RESULTS_ROOT
