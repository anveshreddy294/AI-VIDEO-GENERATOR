# modules/planning/visual_skeleton.py

VISUAL_SKELETON_PROMPT = """
You are a visual content planner for educational videos.

Given a scene description, output a JSON with:
- template: one of [concept_card, chalkboard, equation, diagram, comparison, timeline]
- content: the data to fill into that template

Available templates:
- concept_card: for showing 2-4 connected concepts with visual cards (e.g. CNN layers, phases, components)
- chalkboard: for structural breakdowns with labeled geometric shapes
- equation: for mathematical derivations step by step
- diagram: for system architecture or flow diagrams
- comparison: for A vs B comparisons
- timeline: for sequential historical or process events

Output ONLY valid JSON. Example:
{{
  "template": "concept_card",
  "main_title": "CNN Architecture",
  "cards": [
    {{"title": "Convolution", "content": "Feature extraction\\nSliding filter window", "color": "CHALK_BLUE"}},
    {{"title": "Pooling", "content": "Dimensionality\\nreduction", "color": "CHALK_YELLOW"}},
    {{"title": "Fully Connected", "content": "Classification\\nOutput layer", "color": "CHALK_PINK"}}
  ]
}}

Scene: {scene_description}
"""
