"""Conservative TXT outline containment; never evidence of semantic dependency."""
from __future__ import annotations

from dataclasses import dataclass
import re
from .knowledge_models import ScopedContentUnit
from .security.source_scope import SourceScope

SECTION_LABELS = frozenset({"purpose", "main responsibilities", "suggested api route", "suggested api routes", "rule", "flow"})


@dataclass(frozen=True)
class OutlineNode:
    content_id: str
    sequence_index: int
    level: int
    label: str
    char_start: int
    char_end: int
    position: tuple[int, int]
    section_end: tuple[int, int]
    parent_node: tuple[str, int] | None


def detect_outline(scope: SourceScope, units: list[ScopedContentUnit]) -> list[OutlineNode]:
    """Recognize marked headings only in an ordered, explicitly nested TXT outline."""
    if not units or any((u.user_id, u.source_id, u.source_version) != (scope.user_id, scope.source_id, scope.source_version) for u in units):
        return []
    if any(u.content.modality != "txt" for u in units):
        return []
    ordered = sorted(units, key=lambda u: u.content.sequence_index)
    if len({u.content.sequence_index for u in ordered}) != len(ordered):
        return []
    headings: list[tuple[str, int, int, str, int, int, tuple[int, int]]] = []
    numbered = False
    letters = 0
    title: tuple[str, int, int, str, int, int, tuple[int, int]] | None = None
    for ordinal, unit in enumerate(ordered):
        offset = 0
        for line in unit.content.text.splitlines(keepends=True):
            label = line.strip()
            start = offset + len(line) - len(line.lstrip())
            end = start + len(label)
            number = re.fullmatch(r"\d{1,2}\.\s+(.{2,120})", label)
            letter = re.fullmatch(r"[A-Z]\.\s+(.{2,120})", label)
            level: int | None = None
            visible = label
            if number and number[1].isupper():
                level, visible, numbered = 1, number[1], True
            elif letter and numbered and letter[1].isupper():
                level, visible = 2, letter[1]
                letters += 1
            elif numbered and label.endswith(":") and label[:-1].casefold() in SECTION_LABELS:
                level, visible = 3, label[:-1]
            elif not numbered and title is None and ordinal == 0 and label.isupper() and len(label.split()) >= 3 and len(label) <= 120:
                title = (unit.content_id, unit.content.sequence_index, 0, label, start, end, (ordinal, start))
            if level is not None:
                # Heading evidence spans cover the literal label without its outline marker.
                label_start = start + (len(label) - len(visible) if number or letter else 0)
                headings.append((unit.content_id, unit.content.sequence_index, level, visible, label_start, label_start + len(visible), (ordinal, start)))
            offset += len(line)
    # A single numbered prose/list item or random capitals are not outline authority.
    if not numbered or letters < 2:
        return []
    if title:
        headings.insert(0, title)
    result: list[OutlineNode] = []
    stack: list[tuple[str, int, int]] = []
    for index, (cid, sequence, level, label, start, end, position) in enumerate(headings):
        while stack and stack[-1][2] >= level:
            stack.pop()
        parent = (stack[-1][0], stack[-1][1]) if stack else None
        boundary = next((h[6] for h in headings[index + 1:] if h[2] <= level), (len(ordered), 0))
        result.append(OutlineNode(cid, sequence, level, label, start, end, position, boundary, parent))
        stack.append((cid, start, level))
    return result


def outline_supports_child(nodes: list[OutlineNode], units: list[ScopedContentUnit], parent: str,
                           parent_spans: list[tuple[str, int, int]], child: str,
                           child_spans: list[tuple[str, int, int]]) -> bool:
    """Every cited child span must remain inside the explicitly cited parent's section."""
    ordered = sorted(units, key=lambda u: u.content.sequence_index)
    positions = {u.content_id: i for i, u in enumerate(ordered)}
    contents = {u.content_id: u.content.text for u in ordered}
    if not child_spans or any(cid not in contents for cid, _, _ in child_spans):
        return False
    for node in nodes:
        if " ".join(parent.casefold().split()) != " ".join(node.label.casefold().split()):
            continue
        if not any(cid == node.content_id and start <= node.char_start and end >= node.char_end for cid, start, end in parent_spans):
            continue
        if all(node.position <= (positions[cid], start) and (positions[cid], end) <= node.section_end for cid, start, end in child_spans):
            # Literal label support is mandatory; this helper never invents semantic equivalence.
            from .content_understanding import label_supported
            if any(label_supported(child, contents[cid][start:end]) for cid, start, end in child_spans):
                return True
    return False
