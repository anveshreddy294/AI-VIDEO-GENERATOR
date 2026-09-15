# Concept Dependency Graph

The PageIndex pipeline can emit `concept_graph.json` alongside `structure.json`. Downstream planners and `pageindex_retriever` use it to order explanations and attach **prerequisites** to matched curriculum sections.

## Edge semantics

- **`from`** — prerequisite node (`node_id` of the concept that should be understood first)
- **`to`** — dependent node (`node_id` of the concept that builds on the prerequisite)
- **`relation`** — always `"prerequisite"`

Example: Bohr model depends on Rutherford scattering:

```json
{
  "from": "0005",
  "to": "0007",
  "relation": "prerequisite",
  "source": "curated",
  "weight": 0.9,
  "reason": "Bohr model builds on the nuclear atom"
}
```

## How edges are inferred

| Source | Weight | Meaning |
|--------|--------|---------|
| `chapter_sequence` | ~0.4 | Chapter N precedes chapter N+1; chapter precedes its first section |
| `hierarchical_sequence` | ~0.5 | Section order within a chapter (textbook flow) |
| `curated` | ~0.9 | Domain knowledge rules (chemistry / physics KB in `concept_graph.py`) |
| `semantic_overlap` | variable | Cross-chapter keyword/tag overlap (earlier → later) |

Edges are deduplicated; the highest weight wins per `(from, to)` pair. Prerequisites cannot start after their dependents.

## Regenerate

After indexing or synthesizing a textbook:

```bash
cd PageIndex
PYTHONPATH=. venv/bin/python -m pageindex.concept_graph --doc physics.pdf
PYTHONPATH=. venv/bin/python -m pageindex.concept_graph --all
```

Or use the script wrapper:

```bash
PYTHONPATH=. venv/bin/python scripts/build_concept_graph.py --all
```

The live PDF pipeline (`run_pageindex.py`) writes `concept_graph.json` automatically at the end of `page_index_main` unless disabled via config (`build_concept_graph: false`).

Curated gold-standard trees:

```bash
PYTHONPATH=. venv/bin/python scripts/synthesize_ideal_index.py
```

## Load in Python

```python
from pageindex.results_loader import DocumentArtifacts

arts = DocumentArtifacts.from_pdf_path("examples/documents/physics.pdf")
graph = arts.concept_graph()
prereqs = arts.prerequisites_for("0007")  # node_id of dependent section
```

## Add a new textbook

1. Run `run_pageindex.py --pdf_path ...` **or** add a blueprint to `scripts/synthesize_ideal_index.py` and run synthesis.
2. Ensure `structure.json` passes `semantic_validation.json`.
3. Run `python -m pageindex.concept_graph --doc <folder>.pdf`.
4. Optionally extend `_CHEMISTRY_CURATED` / `_PHYSICS_CURATED` in `pageindex/concept_graph.py` with real prerequisite pairs for your domain.

## Artifacts

| File | Description |
|------|-------------|
| `concept_graph.json` | Nodes + prerequisite edges |
| `pedagogical_metadata.json` | Per-node objectives, tags, visualizable elements |

Both are listed in `results_loader.ARTIFACT_FILES`.
