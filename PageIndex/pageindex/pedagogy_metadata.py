"""Deterministic pedagogical metadata derivation (no LLM by default)."""

from __future__ import annotations

import re
from typing import List, Optional

_TERM_TO_TAG = {
    "atom": "atomic-structure",
    "electron": "subatomic-particles",
    "proton": "subatomic-particles",
    "neutron": "subatomic-particles",
    "cathode": "discharge-tube",
    "discharge": "discharge-tube",
    "rutherford": "nuclear-model",
    "bohr": "bohr-model",
    "isotope": "isotopes",
    "isobar": "isobars",
    "isotone": "isotones",
    "periodic": "periodic-table",
    "mendeleev": "periodic-table",
    "bonding": "chemical-bonding",
    "molecule": "molecules",
    "oxidation": "redox-reactions",
    "reduction": "redox-reactions",
    "redox": "redox-reactions",
    "reaction": "chemical-reactions",
    "experiment": "experiments",
    "configuration": "electron-configuration",
    "orbit": "atomic-orbitals",
    "shell": "electron-shells",
    "table": "reference-table",
    # Physics — mechanics & measurement
    "force": "forces",
    "motion": "kinematics",
    "velocity": "kinematics",
    "acceleration": "kinematics",
    "momentum": "momentum",
    "energy": "energy",
    "work": "work-energy",
    "power": "power",
    "gravitation": "gravitation",
    "gravity": "gravitation",
    "torque": "rotational-motion",
    "rotation": "rotational-motion",
    "vector": "vectors",
    "projectile": "projectile-motion",
    "satellite": "satellites",
    "kepler": "gravitation",
    "newton": "laws-of-motion",
    "friction": "friction",
    "inertia": "inertia",
    "dimension": "dimensional-analysis",
    "measurement": "measurement",
    "unit": "units",
    "collision": "collisions",
    "equilibrium": "equilibrium",
    "circular": "circular-motion",
}

_VISUALIZABLE_OBJECTS = [
    ("discharge tube", "discharge tube"),
    ("gold foil", "gold foil deflection"),
    ("cathode ray", "cathode rays"),
    ("plum pudding", "plum pudding model"),
    ("periodic table", "periodic table"),
    ("bohr", "Bohr atom orbits"),
    ("rutherford", "Rutherford scattering"),
    ("electron configuration", "electron shell diagram"),
    ("conical flask", "conical flask experiment"),
    ("bond", "chemical bond diagram"),
    ("molecule", "molecule model"),
    ("orbit", "electron orbit diagram"),
    ("shell", "electron shell diagram"),
    ("isotope", "isotope comparison"),
    # Physics
    ("velocity-time", "velocity-time graph"),
    ("position-time", "position-time graph"),
    ("free body", "free body diagram"),
    ("projectile", "projectile trajectory"),
    ("vector", "vector diagram"),
    ("torque", "torque diagram"),
    ("satellite", "satellite orbit"),
    ("gravitational", "gravitational field"),
    ("kepler", "planetary orbit"),
    ("spring", "spring-mass system"),
    ("collision", "collision diagram"),
    ("rotational", "rotating rigid body"),
    ("centripetal", "circular motion diagram"),
]


def _slugify(word: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-")


def derive_semantic_tags(
    title: str,
    keywords: Optional[List[str]] = None,
    content_type: Optional[str] = None,
) -> List[str]:
    tags: List[str] = []
    blob = f"{title} {' '.join(keywords or [])}".lower()
    for term, tag in _TERM_TO_TAG.items():
        if term in blob and tag not in tags:
            tags.append(tag)
    if content_type and content_type not in tags:
        tags.append(content_type)
    if not tags and keywords:
        tags = [_slugify(k) for k in keywords[:3] if k]
    if not tags and title:
        tags = [_slugify(w) for w in title.split()[:2] if len(w) > 3]
    return tags[:8] or ["general-concept"]


def derive_learning_objectives(
    title: str,
    child_titles: Optional[List[str]] = None,
) -> List[str]:
    objectives: List[str] = []
    if title:
        objectives.append(f"Understand the key concepts of {title}.")
    for ct in (child_titles or [])[:3]:
        ct = (ct or "").strip()
        if ct:
            objectives.append(f"Explain {ct}.")
    if len(objectives) < 2 and title:
        objectives.append(f"Apply knowledge from {title} to related problems.")
    return objectives[:4]


def derive_visualizable_elements(
    text: str = "",
    keywords: Optional[List[str]] = None,
    title: str = "",
) -> List[str]:
    blob = f"{title} {text} {' '.join(keywords or [])}".lower()
    found: List[str] = []
    for needle, label in _VISUALIZABLE_OBJECTS:
        if needle in blob and label not in found:
            found.append(label)
    for kw in (keywords or [])[:5]:
        if len(kw) > 4 and kw.lower() not in blob:
            continue
        if kw not in found and len(found) < 6:
            found.append(kw)
    return found[:6]


def default_grade_for_domain(domain: Optional[str] = None, doc_name: str = "") -> str:
    """Return a sensible default grade label from domain or document name."""
    blob = f"{domain or ''} {doc_name}".lower()
    if "physics" in blob:
        return "Class XI"
    if "chemistry" in blob or "chem" in blob:
        return "Class X"
    return "Class IX"


def enrich_node_metadata(
    node: dict,
    child_titles: Optional[List[str]] = None,
    *,
    grade_appropriateness: Optional[str] = None,
) -> None:
    """Populate semantic_tags, learning_objectives, visualizable_elements on a node."""
    title = node.get("title") or ""
    keywords = node.get("keywords") or []
    text = node.get("text") or ""
    content_type = node.get("content_type")

    if not node.get("semantic_tags"):
        node["semantic_tags"] = derive_semantic_tags(title, keywords, content_type)
    if not node.get("learning_objectives"):
        node["learning_objectives"] = derive_learning_objectives(title, child_titles)
    if not node.get("visualizable_elements"):
        node["visualizable_elements"] = derive_visualizable_elements(text, keywords, title)
    if not node.get("grade_appropriateness"):
        node["grade_appropriateness"] = grade_appropriateness or "Class IX"
