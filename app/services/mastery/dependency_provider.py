"""Step 5C Dependency Provider — Grounded Prerequisite Evaluation.

Inspects grounded KnowledgeGraph dependencies without fabricating relationships.
Evaluates prerequisite satisfaction and blockage dynamically from mastery states.
"""

from __future__ import annotations

from typing import Any
from ..schemas import KnowledgeGraph


class ConceptDependencyProvider:
    """Provides dependency and prerequisite analysis over grounded concept graphs."""

    def __init__(self, prerequisites_map: dict[str, list[str]] | None = None) -> None:
        # Maps concept_id -> list of prerequisite concept_ids
        self._prereqs: dict[str, list[str]] = {
            cid: list(prereq_ids)
            for cid, prereq_ids in (prerequisites_map or {}).items()
        }

    @classmethod
    def from_knowledge_graph(cls, kg: KnowledgeGraph) -> "ConceptDependencyProvider":
        """Construct dependency provider directly from existing grounded KnowledgeGraph."""
        prereqs: dict[str, list[str]] = {}
        for cid, node in kg.concepts.items():
            clean_cid = cid.strip()
            prereq_list = [p.strip() for p in getattr(node, "prerequisite_concept_ids", []) if p and p.strip()]
            prereqs[clean_cid] = prereq_list
        return cls(prereqs)

    @classmethod
    def from_prerequisites_map(cls, prereqs: dict[str, list[str]]) -> "ConceptDependencyProvider":
        """Construct provider from an explicit concept_id -> [prerequisite_ids] mapping."""
        return cls(prereqs)

    def get_prerequisites(self, concept_id: str) -> list[str]:
        """Return the grounded prerequisite concept IDs for a concept."""
        return list(self._prereqs.get(concept_id.strip(), []))

    def are_dependencies_satisfied(self, concept_id: str, mastered_concept_ids: set[str]) -> bool:
        """Return True if all grounded prerequisites for this concept are MASTERED."""
        prereqs = self.get_prerequisites(concept_id)
        if not prereqs:
            return True
        return all(p in mastered_concept_ids for p in prereqs)

    def get_unsatisfied_dependencies(self, concept_id: str, mastered_concept_ids: set[str]) -> list[str]:
        """Return the list of prerequisite IDs that have not yet been MASTERED."""
        prereqs = self.get_prerequisites(concept_id)
        return [p for p in prereqs if p not in mastered_concept_ids]

    def get_dependents(self, concept_id: str) -> list[str]:
        """Return all concepts that directly declare concept_id as a prerequisite."""
        clean_cid = concept_id.strip()
        dependents = []
        for cid, prereqs in self._prereqs.items():
            if clean_cid in prereqs:
                dependents.append(cid)
        return dependents

    def has_prerequisite(self, concept_a: str, concept_b: str) -> bool:
        """Return True if concept_b is a direct or transitive prerequisite of concept_a."""
        clean_a = concept_a.strip()
        clean_b = concept_b.strip()
        visited = set()
        stack = list(self.get_prerequisites(clean_a))

        while stack:
            curr = stack.pop()
            if curr == clean_b:
                return True
            if curr not in visited:
                visited.add(curr)
                stack.extend(self.get_prerequisites(curr))

        return False
