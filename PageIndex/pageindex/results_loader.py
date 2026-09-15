"""Load canonical PageIndex pipeline artifacts from results/<doc>.pdf/."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import get_pdf_name

_GARBLED_RE = re.compile(r"/G\d{2,3}")

ARTIFACT_FILES = (
    "structure.json",
    "tree_structure.json",
    "tree.json",
    "summaries.json",
    "extracted_pages.json",
    "validated_toc.json",
    "toc_candidates.json",
    "semantic_validation.json",
    "pipeline_metrics.json",
    "summary_cache.json",
    "concept_graph.json",
    "pedagogical_metadata.json",
)


def results_dir_for_pdf(pdf_path: str, results_root: Optional[Path] = None) -> Path:
    """Return results/<basename.pdf>/ — matches page_index_main output layout."""
    root = results_root or Path(__file__).resolve().parent.parent / "results"
    return root / get_pdf_name(pdf_path)


def _is_garbled_ocr(text: str) -> bool:
    if not text:
        return False
    sample = text[:2000]
    hits = len(_GARBLED_RE.findall(sample))
    return hits > 10 and (hits / max(len(sample), 1)) > 0.02


class DocumentArtifacts:
    """Read-only access to one document's pipeline artifacts."""

    def __init__(self, results_dir: Path):
        self.results_dir = Path(results_dir)

    @classmethod
    def from_pdf_path(cls, pdf_path: str, results_root: Optional[Path] = None) -> "DocumentArtifacts":
        return cls(results_dir_for_pdf(pdf_path, results_root))

    def exists(self) -> bool:
        return (self.results_dir / "structure.json").is_file()

    def list_artifacts(self) -> List[str]:
        return [name for name in ARTIFACT_FILES if (self.results_dir / name).is_file()]

    def load(self, filename: str) -> Any:
        path = self.results_dir / filename
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def structure_nodes(self) -> List[dict]:
        data = self.load("structure.json")
        if not data:
            return []
        structure = data.get("structure") or []
        return structure if isinstance(structure, list) else []

    def walk_nodes(self, nodes: Optional[List[dict]] = None) -> List[dict]:
        if nodes is None:
            nodes = self.structure_nodes()
        flat: List[dict] = []
        for node in nodes:
            flat.append(node)
            children = node.get("nodes") or node.get("children") or []
            if children:
                flat.extend(self.walk_nodes(children))
        return flat

    def get_pages(self, start_page: int, end_page: int) -> List[dict]:
        pages = self.load("extracted_pages.json") or []
        lo, hi = min(start_page, end_page), max(start_page, end_page)
        return [p for p in pages if lo <= int(p.get("page", 0)) <= hi]

    def get_page_text(
        self,
        start_page: int,
        end_page: int,
        max_chars: int = 3000,
        skip_garbled: bool = True,
    ) -> str:
        chunks: List[str] = []
        total = 0
        for page in self.get_pages(start_page, end_page):
            text = (page.get("text") or "").strip()
            if not text:
                continue
            if skip_garbled and _is_garbled_ocr(text):
                continue
            header = f"[page {page.get('page')}]"
            block = f"{header}\n{text}"
            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 80:
                    chunks.append(block[:remaining] + "\n...(truncated)")
                break
            chunks.append(block)
            total += len(block)
        return "\n\n".join(chunks)

    def concept_graph(self) -> dict:
        """Load concept_graph.json or return empty dict."""
        return self.load("concept_graph.json") or {}

    def pedagogical_metadata(self) -> dict:
        """Load pedagogical_metadata.json or return empty dict."""
        return self.load("pedagogical_metadata.json") or {}

    def prerequisites_for(self, node_id: str) -> List[dict]:
        """Return prerequisite nodes for *node_id* (edges where to == node_id)."""
        graph = self.concept_graph()
        if not node_id or not graph:
            return []
        id_to_node = {n.get("node_id"): n for n in self.walk_nodes() if n.get("node_id")}
        title_map = {n.get("node_id"): n.get("title") for n in graph.get("nodes") or []}
        out: List[dict] = []
        for edge in graph.get("edges") or []:
            if edge.get("to") != node_id or edge.get("relation") != "prerequisite":
                continue
            fid = edge.get("from")
            if not fid:
                continue
            node = id_to_node.get(fid) or {}
            out.append({
                "node_id": fid,
                "title": title_map.get(fid) or node.get("title") or fid,
                "source": edge.get("source"),
                "reason": edge.get("reason", ""),
            })
        return out

    def dependents_of(self, node_id: str) -> List[dict]:
        """Return nodes that list *node_id* as a prerequisite (edges where from == node_id)."""
        graph = self.concept_graph()
        if not node_id or not graph:
            return []
        id_to_node = {n.get("node_id"): n for n in self.walk_nodes() if n.get("node_id")}
        title_map = {n.get("node_id"): n.get("title") for n in graph.get("nodes") or []}
        out: List[dict] = []
        for edge in graph.get("edges") or []:
            if edge.get("from") != node_id or edge.get("relation") != "prerequisite":
                continue
            tid = edge.get("to")
            if not tid:
                continue
            node = id_to_node.get(tid) or {}
            out.append({
                "node_id": tid,
                "title": title_map.get(tid) or node.get("title") or tid,
                "source": edge.get("source"),
                "reason": edge.get("reason", ""),
            })
        return out
