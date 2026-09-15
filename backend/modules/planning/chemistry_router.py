"""Chemistry template router.

Maps a storyboard scene's (topic, scene_role, semantic_tags, visualizable_elements)
to the most appropriate chemistry template ID.

Called from storyboard._validate_entry to override generic explain/freeform
templates when the topic and retrieved section metadata indicate a chemistry domain.
"""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Domain keyword sets
# ---------------------------------------------------------------------------

_ATOMIC_KEYWORDS = frozenset({
    "atom", "atomic", "bohr", "rutherford", "thomson", "electron",
    "proton", "neutron", "nucleus", "discharge", "cathode", "canal",
    "plum pudding", "scattering", "shell", "orbit", "subatomic",
    "dalton", "chadwick", "goldstein", "millikan",
})

_ELECTRON_CONFIG_KEYWORDS = frozenset({
    "electron configuration", "electronic configuration", "aufbau",
    "pauli", "hund", "orbital", "subshell", "valence", "configuration",
    "atomic number", "mass number", "isotope", "isobar",
})

_PERIODIC_KEYWORDS = frozenset({
    "periodic", "period", "group", "electronegativity", "ionization",
    "ionisation", "atomic radius", "periodic table", "mendeleev",
    "moseley", "trend", "shielding", "effective nuclear",
})

_BONDING_KEYWORDS = frozenset({
    "ionic", "covalent", "bond", "bonding", "electronegativity",
    "electron pair", "lewis", "dot structure", "octet",
})

_IONIC_KEYWORDS = frozenset({
    "ionic", "ion", "cation", "anion", "lattice", "electrostatic",
    "transfer", "nacl", "sodium chloride",
})

_COVALENT_KEYWORDS = frozenset({
    "covalent", "shared", "sharing", "molecule", "h2o", "co2",
    "water", "carbon dioxide", "double bond", "triple bond",
})

_REDOX_KEYWORDS = frozenset({
    "redox", "oxidation", "reduction", "oxidizing", "reducing",
    "electron transfer", "ox", "red", "half reaction", "oxidation state",
    "oxidation number",
})

_EQUILIBRIUM_KEYWORDS = frozenset({
    "equilibrium", "reversible", "le chatelier", "kc", "kp",
    "dynamic equilibrium",
})

_ACID_BASE_KEYWORDS = frozenset({
    "acid", "base", "ph", "neutralisation", "neutralization",
    "proton donor", "bronsted", "lowry", "arrhenius",
})

_ENERGY_KEYWORDS = frozenset({
    "enthalpy", "exothermic", "endothermic", "activation energy",
    "reaction energy", "hess", "bond energy",
})

_GEOMETRY_KEYWORDS = frozenset({
    "molecular geometry", "vsepr", "shape", "linear", "tetrahedral",
    "bent", "trigonal", "molecular structure",
})

# ---------------------------------------------------------------------------
# Tag-to-template mapping (highest priority — explicit tags)
# ---------------------------------------------------------------------------

_TAG_TO_TEMPLATE: dict[str, str] = {
    # Atomic structure tags — mapped to the most specific available template
    "atomic-structure":       "atomic_structure",
    "nuclear-model":          "rutherford_gold_foil",   # Rutherford's nuclear model
    "electron-configuration": "electron_configuration", # dedicated shell-filling template
    # Periodic / bonding / reaction tags
    "periodic-table":         "periodic_trends",
    "ionic-bonding":          "ionic_bonding",
    "covalent-bonding":       "covalent_bonding",
    "chemical-bonding":       "covalent_bonding",       # generic bonding defaults to covalent
    "redox":                  "redox_transfer",
    "acid-base":              "acid_base",
    "chemical-equilibrium":   "chemical_equilibrium",
    "reaction-energy":        "reaction_energy",
    "molecular-geometry":     "molecular_geometry",
}

# Priority ordering for tag matching — more specific tags take precedence.
_TAG_PRIORITY_ORDER = [
    "ionic-bonding", "covalent-bonding",
    "nuclear-model",          # before atomic-structure so Rutherford gets dedicated template
    "electron-configuration", # before atomic-structure so shell filling gets dedicated template
    "atomic-structure",
    "periodic-table", "redox", "acid-base",
    "chemical-equilibrium", "reaction-energy", "molecular-geometry",
    "chemical-bonding",       # least specific bonding tag — checked last
]

# ---------------------------------------------------------------------------
# Bohr-specific keyword set (subset of _ATOMIC_KEYWORDS, for finer routing)
# ---------------------------------------------------------------------------

_BOHR_KEYWORDS = frozenset({
    "bohr", "bohr model", "bohr's model", "energy level", "energy levels",
    "quantised", "quantized", "orbit", "orbits", "shell transition",
    "emission", "absorption", "spectral line", "hydrogen spectrum",
})

_RUTHERFORD_KEYWORDS = frozenset({
    "rutherford", "gold foil", "alpha particle", "nuclear model",
    "nucleus", "scattering", "deflection", "canal ray",
    "discharge tube", "plum pudding",
})

_ELECTRON_CONFIG_KEYWORDS_FINE = frozenset({
    "electron configuration", "electronic configuration", "aufbau",
    "pauli exclusion", "hund", "subshell", "orbital filling",
    "2n squared", "k shell", "l shell", "m shell", "valence electrons",
})

# ---------------------------------------------------------------------------
# scene_role → template preference lists (used as tie-breakers)
# ---------------------------------------------------------------------------

_ROLE_PREFERENCE: dict[str, list[str]] = {
    "hook": [
        "rutherford_gold_foil", "bohr_orbit", "atomic_structure", "periodic_trends",
    ],
    "visual_intuition": [
        "bohr_orbit", "atomic_structure", "rutherford_gold_foil",
        "ionic_bonding", "covalent_bonding", "periodic_trends",
    ],
    "formal_concept": [
        "bohr_orbit", "electron_configuration", "atomic_structure",
        "periodic_trends", "ionic_bonding", "covalent_bonding",
    ],
    "worked_example": [
        "redox_transfer", "acid_base", "chemical_equilibrium", "reaction_energy",
        "electron_configuration",
    ],
    "summary": [
        "atomic_structure", "bohr_orbit",
    ],
}

# All valid chemistry template IDs — kept in sync with chemistry/__init__.py.
CHEMISTRY_TEMPLATE_IDS = [
    "atomic_structure",
    "periodic_trends",
    "ionic_bonding",
    "covalent_bonding",
    "molecular_geometry",
    "chemical_equilibrium",
    "acid_base",
    "reaction_energy",
    # Specific atomic-model templates
    "rutherford_gold_foil",
    "bohr_orbit",
    "electron_configuration",
    "redox_transfer",
]


def route_chemistry_template(
    topic: str,
    scene_role: str,
    semantic_tags: list[str],
    visualizable_elements: list[str],
) -> Optional[str]:
    """Return the best chemistry template ID, or None if topic is not chemistry.

    Priority:
      1. Explicit semantic_tag match (strongest signal from indexer)
      2. visualizable_elements keyword match
      3. Topic keyword domain detection
      4. scene_role preference within the matched domain
    """
    topic_lower = topic.lower()
    tags_lower = [t.lower() for t in semantic_tags]
    vis_lower = [v.lower() for v in visualizable_elements]
    combined = topic_lower + " " + " ".join(tags_lower) + " " + " ".join(vis_lower)

    def _kw_hit(keyword_set: frozenset, text: str) -> bool:
        """Simple substring check (fast path used before full word-boundary match)."""
        return any(kw in text for kw in keyword_set)

    # 1. Explicit tag override — use priority order (specific before generic).
    #    For the "atomic-structure" tag, refine further with Bohr/Rutherford keywords
    #    so that topic-specific templates are preferred over the generic one.
    for priority_tag in _TAG_PRIORITY_ORDER:
        if priority_tag in tags_lower:
            base = _TAG_TO_TEMPLATE[priority_tag]
            if base == "atomic_structure":
                # Refine: Bohr-specific topic → bohr_orbit
                if _kw_hit(_BOHR_KEYWORDS, combined):
                    return "bohr_orbit"
                # Refine: Rutherford-specific topic → rutherford_gold_foil
                if _kw_hit(_RUTHERFORD_KEYWORDS, combined):
                    return "rutherford_gold_foil"
                # Refine: electron config specifics → electron_configuration
                if _kw_hit(_ELECTRON_CONFIG_KEYWORDS_FINE, combined):
                    return "electron_configuration"
            return base

    # 2. Visualizable elements — route to the most specific atomic template
    _vis_to_template = {
        "bohr atom orbits":       "bohr_orbit",
        "bohr model":             "bohr_orbit",
        "energy levels":          "bohr_orbit",
        "shell transition":       "bohr_orbit",
        "gold foil experiment":   "rutherford_gold_foil",
        "rutherford":             "rutherford_gold_foil",
        "alpha particle":         "rutherford_gold_foil",
        "nuclear model":          "rutherford_gold_foil",
        "discharge tube":         "atomic_structure",
        "plum pudding model":     "atomic_structure",
        "electron shell":         "electron_configuration",
        "shell filling":          "electron_configuration",
    }
    for ve in vis_lower:
        for vis_key, tmpl in _vis_to_template.items():
            if vis_key in ve:
                return tmpl

    def _kw_match(keyword_set: frozenset, text: str) -> bool:
        """Word-boundary match any keyword from a set against text."""
        for kw in keyword_set:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return True
        return False

    # 3. Fine-grained atomic-model routing (before generic atomic keyword check)
    #    Bohr-specific → bohr_orbit; Rutherford-specific → rutherford_gold_foil
    if _kw_match(_BOHR_KEYWORDS, combined):
        prefs = _ROLE_PREFERENCE.get(scene_role, [])
        for p in prefs:
            if p in ("bohr_orbit", "atomic_structure"):
                return p
        return "bohr_orbit"

    if _kw_match(_RUTHERFORD_KEYWORDS, combined):
        return "rutherford_gold_foil"

    # 4. Electron configuration (dedicated shell-filling template)
    if _kw_match(_ELECTRON_CONFIG_KEYWORDS_FINE, combined) or _kw_match(_ELECTRON_CONFIG_KEYWORDS, combined):
        return "electron_configuration"

    # 5. General atomic structure keyword match
    if _kw_match(_ATOMIC_KEYWORDS, combined):
        prefs = _ROLE_PREFERENCE.get(scene_role, [])
        for p in prefs:
            if p in ("bohr_orbit", "atomic_structure", "rutherford_gold_foil"):
                return p
        return "atomic_structure"

    if _kw_match(_REDOX_KEYWORDS, combined):
        return "redox_transfer"

    if _kw_match(_IONIC_KEYWORDS, combined):
        return "ionic_bonding"

    if _kw_match(_COVALENT_KEYWORDS, combined):
        return "covalent_bonding"

    if _kw_match(_BONDING_KEYWORDS, combined):
        if scene_role in ("visual_intuition", "hook"):
            return "ionic_bonding"
        return "covalent_bonding"

    if _kw_match(_PERIODIC_KEYWORDS, combined):
        return "periodic_trends"

    if _kw_match(_ACID_BASE_KEYWORDS, combined):
        return "acid_base"

    if _kw_match(_EQUILIBRIUM_KEYWORDS, combined):
        return "chemical_equilibrium"

    if _kw_match(_ENERGY_KEYWORDS, combined):
        return "reaction_energy"

    if _kw_match(_GEOMETRY_KEYWORDS, combined):
        return "molecular_geometry"

    return None


def is_chemistry_topic(
    topic: str,
    semantic_tags: list[str],
    visualizable_elements: list[str],
) -> bool:
    """Return True if the topic and retrieved metadata indicate a chemistry domain."""
    return route_chemistry_template(topic, "formal_concept", semantic_tags, visualizable_elements) is not None
