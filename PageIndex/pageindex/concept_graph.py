"""Concept dependency graph generation from PageIndex structure trees.

Edges use ``from`` = prerequisite node_id, ``to`` = dependent node_id,
``relation`` = ``prerequisite`` (compatible with pageindex_retriever).

Regenerate after indexing:
    PYTHONPATH=. python -m pageindex.concept_graph --doc physics.pdf
    PYTHONPATH=. python -m pageindex.concept_graph --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = "1.0"
EDGE_RELATION = "prerequisite"

# Curated prerequisite rules: dependent pattern -> list of (prereq pattern, reason)
# Patterns match against lowercased title + keywords + semantic_tags.
_CHEMISTRY_CURATED: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "proton and canal",
        [("discharge tube", "Electron discovery precedes canal-ray proton work")],
    ),
    (
        "plum pudding",
        [("discharge tube", "Electrons must be known before atomic models")],
    ),
    (
        "rutherford",
        [
            ("plum pudding", "Rutherford scattering refuted the plum pudding model"),
            ("discharge tube", "Subatomic particles are prerequisite to scattering models"),
        ],
    ),
    (
        "neutron",
        [("rutherford", "Nuclear model precedes discovery of the neutron")],
    ),
    (
        "bohr",
        [
            ("rutherford", "Bohr model builds on the nuclear atom"),
            ("neutron", "Complete subatomic picture informs atomic models"),
        ],
    ),
    (
        "atomic number",
        [("bohr", "Atomic number follows from nuclear charge understanding")],
    ),
    (
        "electron configuration",
        [
            ("bohr", "Shell model underpins electron configuration"),
            ("atomic number", "Atomic number defines electron count"),
        ],
    ),
    (
        "isotope",
        [("atomic number", "Isotopes are defined by constant atomic number")],
    ),
    (
        "isobar",
        [("isotope", "Isobars contrast with isotopes via mass number")],
    ),
    (
        "modern periodic",
        [("atomic number", "Modern periodic law is based on atomic number")],
    ),
    (
        "groups and periods",
        [("modern periodic", "Group/period layout follows the modern law")],
    ),
    (
        "periodic trend",
        [
            ("groups and periods", "Trends are read from table structure"),
            ("electron configuration", "Valence shells explain periodic trends"),
        ],
    ),
    (
        "octet",
        [("electron configuration", "Octet rule uses valence electron count")],
    ),
    (
        "ionic bond",
        [("octet", "Ionic bonding aims at stable electron configurations")],
    ),
    (
        "covalent bond",
        [("octet", "Covalent sharing also seeks stable configurations")],
    ),
    (
        "electronegativity",
        [("covalent bond", "Bond polarity builds on covalent bonding")],
    ),
    (
        "valency",
        [("ionic bond", "Valency counts electrons transferred or shared")],
    ),
    (
        "chemical formulae",
        [("valency", "Formulae are written using valency rules")],
    ),
    (
        "balancing",
        [("conservation of mass", "Balancing respects atom conservation")],
    ),
    (
        "oxidation and reduction",
        [("balancing", "Redox reasoning uses balanced equations")],
    ),
    (
        "oxidation number",
        [("oxidation and reduction", "Oxidation numbers formalise redox")],
    ),
]

_PHYSICS_CURATED: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "instantaneous velocity",
        [("introduction", "Position and displacement precede velocity")],
    ),
    (
        "acceleration",
        [("instantaneous velocity", "Acceleration is the rate of change of velocity")],
    ),
    (
        "kinematic",
        [("acceleration", "Kinematic equations require acceleration concepts")],
    ),
    (
        "scalars and vectors",
        [("introduction", "Plane motion extends straight-line ideas")],
    ),
    (
        "resolution of vectors",
        [("scalars and vectors", "Components require vector basics")],
    ),
    (
        "vector addition",
        [("resolution of vectors", "Analytical addition uses components")],
    ),
    (
        "motion in a plane",
        [
            ("motion in a straight line", "2D motion generalises 1D kinematics"),
            ("vector addition", "Plane motion uses vector tools"),
        ],
    ),
    (
        "projectile",
        [
            ("motion in a plane", "Projectile motion is 2D kinematics"),
            ("resolution of vectors", "Range and height use vector components"),
        ],
    ),
    (
        "uniform circular",
        [
            ("motion in a plane", "Circular motion is motion in a plane"),
            ("acceleration", "Centripetal acceleration changes direction"),
        ],
    ),
    (
        "law of inertia",
        [("introduction", "Inertia follows from describing motion and force")],
    ),
    (
        "newton's first",
        [("law of inertia", "First law is the law of inertia")],
    ),
    (
        "newton's second",
        [("newton's first", "Second law quantifies what first law describes qualitatively")],
    ),
    (
        "newton's third",
        [("newton's second", "Third law pairs with force–acceleration reasoning")],
    ),
    (
        "conservation of momentum",
        [
            ("newton's third", "Momentum conservation follows from action–reaction"),
            ("newton's second", "Impulse and momentum use F = ma"),
        ],
    ),
    (
        "equilibrium",
        [("newton's first", "Equilibrium is net force zero (first law)")],
    ),
    (
        "common forces",
        [("newton's second", "Force diagrams apply F = ma")],
    ),
    (
        "circular motion",
        [
            ("uniform circular", "Dynamics of circular paths needs centripetal ideas"),
            ("newton's second", "Centripetal force comes from F = ma"),
        ],
    ),
    (
        "work",
        [("newton's second", "Work links force and displacement")],
    ),
    (
        "kinetic energy",
        [("work", "Work–energy theorem connects work and KE")],
    ),
    (
        "potential energy",
        [("kinetic energy", "Mechanical energy combines KE and PE")],
    ),
    (
        "conservation of mechanical",
        [
            ("potential energy", "Energy conservation uses both KE and PE"),
            ("work", "Work done relates to energy change"),
        ],
    ),
    (
        "power",
        [("work", "Power is the rate of doing work")],
    ),
    (
        "collision",
        [
            ("conservation of momentum", "Collisions apply momentum conservation"),
            ("kinetic energy", "Elastic vs inelastic uses kinetic energy"),
        ],
    ),
    (
        "centre of mass",
        [("newton's second", "CM motion uses Newton's laws for systems")],
    ),
    (
        "torque",
        [
            ("vector product", "Torque is a cross product"),
            ("centre of mass", "Rotation about CM simplifies dynamics"),
        ],
    ),
    (
        "angular momentum",
        [
            ("torque", "Angular momentum changes with torque"),
            ("moment of inertia", "Rotational inertia appears in L = Iω"),
        ],
    ),
    (
        "moment of inertia",
        [("centre of mass", "Rotational inertia depends on mass distribution")],
    ),
    (
        "rotational motion",
        [
            ("moment of inertia", "τ = Iα requires moment of inertia"),
            ("angular momentum", "Rotational kinematics links to L"),
        ],
    ),
    (
        "kepler",
        [("universal law", "Kepler's laws are explained by gravitation")],
    ),
    (
        "universal law",
        [
            ("newton's second", "Gravitational force obeys F = ma"),
            ("motion in a plane", "Orbital motion is plane motion under a central force"),
        ],
    ),
    (
        "acceleration due to gravity",
        [("universal law", "g follows from GM/R²")],
    ),
    (
        "gravitational potential",
        [("universal law", "Potential energy derives from gravitational force")],
    ),
    (
        "escape speed",
        [("gravitational potential", "Escape energy uses gravitational PE")],
    ),
    (
        "earth satellite",
        [
            ("universal law", "Satellite motion is gravitationally bound orbits"),
            ("uniform circular", "Circular orbits use centripetal gravitation"),
        ],
    ),
]

_DOMAIN_CURATED = {
    "chemistry": _CHEMISTRY_CURATED,
    "physics": _PHYSICS_CURATED,
}


def detect_domain(doc_name: str = "", structure: Optional[List[dict]] = None) -> str:
    blob = (doc_name or "").lower()
    if "chem" in blob:
        return "chemistry"
    if "phys" in blob:
        return "physics"
    if structure:
        tags: List[str] = []
        for n in walk_nodes(structure):
            tags.extend(t.lower() for t in (n.get("semantic_tags") or []))
        tag_blob = " ".join(tags)
        if any(t in tag_blob for t in ("atomic-structure", "redox-reactions", "chemical-bonding")):
            return "chemistry"
        if any(t in tag_blob for t in ("kinematics", "gravitation", "laws-of-motion", "vectors")):
            return "physics"
    return "general"


def walk_nodes(structure: List[dict]) -> List[dict]:
    flat: List[dict] = []
    for node in structure:
        flat.append(node)
        children = node.get("children") or node.get("nodes") or []
        flat.extend(walk_nodes(children))
    return flat


def _node_blob(node: dict) -> str:
    parts = [
        node.get("title") or "",
        " ".join(node.get("keywords") or []),
        " ".join(node.get("semantic_tags") or []),
    ]
    return " ".join(parts).lower()


def _start_page(node: dict) -> int:
    return int(node.get("start_page") or node.get("start_index") or 0)


def _chapter_key(node: dict) -> str:
    struct = str(node.get("structure") or "")
    if struct:
        return struct.split(".")[0]
    return node.get("node_id") or ""


def _keyword_overlap(a: dict, b: dict) -> float:
    ka = set((a.get("keywords") or []) + (a.get("semantic_tags") or []))
    kb = set((b.get("keywords") or []) + (b.get("semantic_tags") or []))
    ka = {x.lower() for x in ka if x}
    kb = {x.lower() for x in kb if x}
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / max(len(ka | kb), 1)


def _edge_key(fr: str, to: str) -> Tuple[str, str]:
    return (fr, to)


def _add_edge(
    edges: Dict[Tuple[str, str], dict],
    fr: str,
    to: str,
    *,
    source: str,
    weight: float,
    reason: str = "",
) -> None:
    if not fr or not to or fr == to:
        return
    key = _edge_key(fr, to)
    existing = edges.get(key)
    payload = {
        "from": fr,
        "to": to,
        "relation": EDGE_RELATION,
        "source": source,
        "weight": round(weight, 3),
    }
    if reason:
        payload["reason"] = reason
    if existing is None or weight > existing.get("weight", 0):
        edges[key] = payload
    elif reason and not existing.get("reason"):
        existing["reason"] = reason


def _chapter_sequence_edges(nodes: List[dict], edges: Dict[Tuple[str, str], dict]) -> None:
    chapters = [n for n in nodes if n.get("content_type") == "chapter"]
    chapters.sort(key=_start_page)
    for i in range(len(chapters) - 1):
        a, b = chapters[i], chapters[i + 1]
        _add_edge(
            edges,
            a.get("node_id", ""),
            b.get("node_id", ""),
            source="chapter_sequence",
            weight=0.4,
            reason="Later chapter builds on earlier chapters",
        )
        # chapter -> first section
        ch_children = [
            c for c in nodes
            if c.get("parent_id") == a.get("node_id") and c.get("content_type") == "section"
        ]
        if ch_children:
            ch_children.sort(key=_start_page)
            _add_edge(
                edges,
                a.get("node_id", ""),
                ch_children[0].get("node_id", ""),
                source="chapter_sequence",
                weight=0.35,
                reason="Chapter overview precedes its sections",
            )


def _hierarchical_sequence_edges(nodes: List[dict], edges: Dict[Tuple[str, str], dict]) -> None:
    by_chapter: Dict[str, List[dict]] = {}
    for n in nodes:
        if n.get("content_type") == "preface":
            continue
        by_chapter.setdefault(_chapter_key(n), []).append(n)

    for ch_nodes in by_chapter.values():
        ordered = sorted(ch_nodes, key=lambda x: (_start_page(x), x.get("level") or 1))
        for i in range(len(ordered) - 1):
            prev, nxt = ordered[i], ordered[i + 1]
            if prev.get("level", 1) == 1 and nxt.get("level", 1) == 1:
                continue
            fid, tid = prev.get("node_id"), nxt.get("node_id")
            if not fid or not tid:
                continue
            if _start_page(prev) > _start_page(nxt):
                continue
            _add_edge(
                edges,
                fid,
                tid,
                source="hierarchical_sequence",
                weight=0.5,
                reason="Textbook section order implies prerequisite flow",
            )


def _curated_edges(
    nodes: List[dict],
    edges: Dict[Tuple[str, str], dict],
    domain: str,
) -> None:
    rules = _DOMAIN_CURATED.get(domain, [])
    if not rules:
        return
    indexed = [(n, _node_blob(n)) for n in nodes if n.get("node_id")]
    for dep_node, dep_blob in indexed:
        for dep_pat, prereq_specs in rules:
            if dep_pat not in dep_blob:
                continue
            for prereq_pat, reason in prereq_specs:
                for pre_node, pre_blob in indexed:
                    if pre_node.get("node_id") == dep_node.get("node_id"):
                        continue
                    if prereq_pat not in pre_blob:
                        continue
                    if _start_page(pre_node) > _start_page(dep_node):
                        continue
                    _add_edge(
                        edges,
                        pre_node.get("node_id", ""),
                        dep_node.get("node_id", ""),
                        source="curated",
                        weight=0.9,
                        reason=reason,
                    )


def _semantic_overlap_edges(
    nodes: List[dict],
    edges: Dict[Tuple[str, str], dict],
    *,
    threshold: float = 0.15,
    max_per_node: int = 3,
) -> None:
    candidates = [
        n for n in nodes
        if n.get("content_type") not in ("preface",) and n.get("node_id")
    ]
    for i, dep in enumerate(candidates):
        dep_page = _start_page(dep)
        overlaps: List[Tuple[float, dict]] = []
        for pre in candidates:
            if pre.get("node_id") == dep.get("node_id"):
                continue
            if _chapter_key(pre) == _chapter_key(dep) and pre.get("level") == dep.get("level"):
                continue
            if _start_page(pre) >= dep_page:
                continue
            score = _keyword_overlap(pre, dep)
            if score >= threshold:
                overlaps.append((score, pre))
        overlaps.sort(key=lambda x: x[0], reverse=True)
        for score, pre in overlaps[:max_per_node]:
            _add_edge(
                edges,
                pre.get("node_id", ""),
                dep.get("node_id", ""),
                source="semantic_overlap",
                weight=score,
                reason="Shared keywords and tags suggest conceptual dependency",
            )


def build_concept_graph(
    structure: List[dict],
    doc_name: str,
    domain: Optional[str] = None,
) -> dict:
    """Build a concept dependency graph from a structure tree."""
    nodes = walk_nodes(structure)
    domain = domain or detect_domain(doc_name, structure)
    edges_map: Dict[Tuple[str, str], dict] = {}

    _chapter_sequence_edges(nodes, edges_map)
    _hierarchical_sequence_edges(nodes, edges_map)
    _curated_edges(nodes, edges_map, domain)
    _semantic_overlap_edges(nodes, edges_map)

    graph_nodes = [
        {
            "node_id": n.get("node_id"),
            "title": n.get("title"),
            "structure": n.get("structure"),
            "level": n.get("level"),
            "content_type": n.get("content_type"),
            "keywords": n.get("keywords") or [],
            "semantic_tags": n.get("semantic_tags") or [],
        }
        for n in nodes
        if n.get("node_id")
    ]
    edge_list = sorted(edges_map.values(), key=lambda e: (e["to"], -e["weight"], e["from"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "doc_name": doc_name,
        "domain": domain,
        "edge_semantics": "from = prerequisite node_id, to = dependent node_id",
        "nodes": graph_nodes,
        "edges": edge_list,
        "stats": {
            "node_count": len(graph_nodes),
            "edge_count": len(edge_list),
            "by_source": _count_by_source(edge_list),
        },
    }


def _count_by_source(edges: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for e in edges:
        src = e.get("source") or "unknown"
        counts[src] = counts.get(src, 0) + 1
    return counts


def build_pedagogical_metadata(structure: List[dict], doc_name: str) -> dict:
    """Build per-node pedagogical metadata from structure (deterministic)."""
    from .pedagogy_metadata import (
        default_grade_for_domain,
        derive_learning_objectives,
        derive_semantic_tags,
        derive_visualizable_elements,
    )

    domain = detect_domain(doc_name, structure)
    grade = default_grade_for_domain(domain, doc_name)
    nodes = walk_nodes(structure)
    per_node: Dict[str, dict] = {}
    for n in nodes:
        nid = n.get("node_id")
        if not nid:
            continue
        child_titles = [
            (c.get("title") or "").strip()
            for c in (n.get("children") or n.get("nodes") or [])
        ]
        per_node[nid] = {
            "title": n.get("title"),
            "learning_objectives": n.get("learning_objectives")
            or derive_learning_objectives(n.get("title") or "", child_titles),
            "semantic_tags": n.get("semantic_tags")
            or derive_semantic_tags(n.get("title") or "", n.get("keywords")),
            "visualizable_elements": n.get("visualizable_elements")
            or derive_visualizable_elements("", n.get("keywords"), n.get("title") or ""),
            "common_misconceptions": n.get("common_misconceptions") or [],
            "grade_appropriateness": n.get("grade_appropriateness") or grade,
        }
    chapter_titles = [n.get("title") for n in nodes if n.get("content_type") == "chapter"]
    return {
        "schema_version": SCHEMA_VERSION,
        "doc_name": doc_name,
        "domain": domain,
        "doc_summary": (
            f"Curriculum tree for {doc_name}: {len(nodes)} nodes, "
            f"{len(chapter_titles)} chapters."
        ),
        "primary_topics": [t for t in chapter_titles if t],
        "nodes": per_node,
    }


def write_concept_graph(
    results_dir: Path | str,
    structure: Optional[List[dict]] = None,
    doc_name: Optional[str] = None,
    *,
    write_pedagogy: bool = True,
) -> dict:
    """Write concept_graph.json (and optionally pedagogical_metadata.json)."""
    results_dir = Path(results_dir)
    if structure is None:
        struct_path = results_dir / "structure.json"
        if not struct_path.is_file():
            raise FileNotFoundError(f"structure.json not found in {results_dir}")
        with open(struct_path, encoding="utf-8") as f:
            data = json.load(f)
        structure = data.get("structure") or []
        doc_name = doc_name or data.get("doc_name") or results_dir.name

    doc_name = doc_name or results_dir.name
    graph = build_concept_graph(structure, doc_name)
    graph_path = results_dir / "concept_graph.json"
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    if write_pedagogy:
        ped = build_pedagogical_metadata(structure, doc_name)
        ped_path = results_dir / "pedagogical_metadata.json"
        with open(ped_path, "w", encoding="utf-8") as f:
            json.dump(ped, f, ensure_ascii=False, indent=2)

    return graph


def _results_root() -> Path:
    return Path(__file__).resolve().parent.parent / "results"


def _cli_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build concept_graph.json from structure.json")
    parser.add_argument("--doc", help="Results folder name (e.g. physics.pdf)")
    parser.add_argument("--all", action="store_true", help="Process every folder with structure.json")
    parser.add_argument("--results-root", type=Path, default=_results_root())
    parser.add_argument("--no-pedagogy", action="store_true", help="Skip pedagogical_metadata.json")
    args = parser.parse_args(argv)

    if not args.doc and not args.all:
        parser.error("Specify --doc <folder> or --all")

    folders: List[Path] = []
    if args.all:
        folders = sorted(
            p for p in args.results_root.iterdir()
            if p.is_dir() and (p / "structure.json").is_file()
        )
    else:
        folders = [args.results_root / args.doc]

    for folder in folders:
        if not (folder / "structure.json").is_file():
            print(f"SKIP (no structure.json): {folder}", file=sys.stderr)
            continue
        graph = write_concept_graph(
            folder,
            write_pedagogy=not args.no_pedagogy,
        )
        print(
            f"Wrote {folder / 'concept_graph.json'} "
            f"(nodes={graph['stats']['node_count']} edges={graph['stats']['edge_count']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
