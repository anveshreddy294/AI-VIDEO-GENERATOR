# VisualAI Knowledge Atelier — Frontend Visual, Motion & Asset Audit

**Repository:** `AI-VIDEO-GENERATOR`  
**Branch:** `integration/knowledge-atelier-api`  
**Frontend Directory:** `newfront/`  
**Date:** October 2026  
**Auditor:** Principal Creative Frontend Engineer & Senior React Reliability Architect  

---

## 1. Executive Summary

A comprehensive visual, layout, asset usage, and motion audit was conducted across all public and authenticated surfaces of VisualAI: The Knowledge Atelier. The application possesses a distinctive, high-end editorial identity rooted in archival scientific scholarship (warm canvas `#EAE7DF`, deep charcoal `#1C1917`, Terracotta `#A46047`, and sharp architectural radii).

However, the audit revealed two primary visual limitations:
1. **Severe Asset Repetition & Orphaned High-Res Plates:** Across 22 assets in `public/assets/`, only 9 images were used while 13 custom specimen plates sat completely idle. As a result, the same 4–5 generic stock photos (`study_desk_mac.jpg`, `library_books_hall.jpg`, `student_studying.jpg`, `notebook_handwritten.jpg`) were repeated up to 6 times across landing, demo, authentication, and source library views.
2. **Static Educational Presentation:** Despite rich mathematical formulas and topological graphs returned by the backend, views lacked coordinated entrance motion, SVG stroke drawing, interactive card feedback, and animated pedagogical progress.

---

## 2. Complete Asset Usage Inventory

The following matrix documents all 22 image assets present in `newfront/public/assets/`:

| Filename | Dimensions | File Size | Initial Reference Count | Initial Locations | Visual Subject | Status / Action |
| :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| `act4_learning_experience.jpg` | 1376x768 | 756.7 KB | 0 | *Unused* | Interactive Lecture & Studio Stage | Assigned to Transformation Stage 4 (Interactive Lessons) |
| `astronomy_telescope_galaxy.jpg` | 1200x798 | 123.3 KB | 3 | Landing (3x) | Deep Field Optical Telescope | Dedicated to Astrophysics Curriculum Specimen |
| `biology_cell_microscope.jpg` | 1200x800 | 104.0 KB | 1 | Landing (1x) | Cellular Micrograph | Dedicated to Biology Curriculum Specimen |
| `chapter_evidence.jpg` | 1376x768 | 693.5 KB | 0 | *Unused* | Mathematical Evidence & Proof Archive | Assigned to Transformation Stage 2 (Topic Extraction) |
| `chapter_knowledge.jpg` | 1376x768 | 694.6 KB | 0 | *Unused* | Topological Knowledge Graph | Assigned to Transformation Stage 3 (Knowledge Roadmap) |
| `chapter_mastery.jpg` | 1376x768 | 633.3 KB | 0 | *Unused* | Diagnostic Assessment & Exam Review | Assigned to Transformation Stage 5 (Practice & Mastery) |
| `chapter_source.jpg` | 1376x768 | 974.8 KB | 0 | *Unused* | Primary Architectural Textbook Ingestion | Assigned to Transformation Stage 1 (Source Ingestion) |
| `database_code_screen.jpg` | 1200x800 | 179.6 KB | 4 | Landing, Transformation, HowItWorks, Demo | Terminal & Query Code Display | Dedicated to Computer Science Indexing Specimen |
| `hero_celestial_botanical.jpg` | 1376x768 | 944.3 KB | 1 | Landing Hero Mount | Archival Botanical & Celestial Collage | Kept as Hero Central Optical Knowledge Stage |
| `library_books_hall.jpg` | 1200x800 | 282.7 KB | 6 | Landing (2x), Trans (2x), Platform, HowItWorks | Classical University Library Stacks | Dedicated to Library Call-to-Action Archive |
| `math_geometry_compass.jpg` | 1200x800 | 70.9 KB | 0 | *Unused* | Brass Drafting Compass on Grid | Assigned to HowItWorks Technical Geometry Plate |
| `notebook_handwritten.jpg` | 1200x800 | 78.0 KB | 4 | Landing (2x), Trans (1x), HowItWorks | Ruled Student Notebook Notes | Dedicated to Study Notes Panel |
| `physics_blackboard.jpg` | 1200x800 | 178.2 KB | 3 | Landing (2x), Platform (1x) | Academic Physics Derivation Board | Dedicated to Physics Calculus Specimen |
| `plate_interferometer.jpg` | 1376x768 | 634.4 KB | 0 | *Unused* | Optical Laser Interferometry Specimen | Assigned to Corridor Stream Plate (Interferometry) |
| `plate_quantum.jpg` | 1376x768 | 870.4 KB | 0 | *Unused* | Quantum State Probability Density | Assigned to Corridor Stream Plate (Quantum) |
| `plate_tensor.jpg` | 1376x768 | 762.3 KB | 0 | *Unused* | Tensor Mathematical Surface | Assigned to Platform Instrument Plate (Tensors) |
| `specimen_analog_notebook.jpg` | 1376x768 | 760.9 KB | 0 | *Unused* | Analog Laboratory Ledger Notebook | Assigned to Hero Satellite 2 & Review Stage |
| `specimen_biology_dna.jpg` | 1376x768 | 758.5 KB | 0 | *Unused* | Molecular DNA Double-Helix Specimen | Assigned to Corridor Stream Plate (Biology DNA) |
| `specimen_math_wave.jpg` | 1376x768 | 842.9 KB | 0 | *Unused* | Harmonic Wave Mechanics Oscillation | Assigned to Corridor Stream Plate (Harmonic Wave) |
| `specimen_physics_orbit.jpg` | 1376x768 | 794.1 KB | 0 | *Unused* | Gravitational Orbital Dynamics | Assigned to Hero Satellite 1 (Celestial Mechanics) |
| `student_studying.jpg` | 1200x800 | 146.9 KB | 4 | Landing, Trans, Platform, HowItWorks | Student Focused Study Session | Preserved in SignIn Educational Context |
| `study_desk_mac.jpg` | 1200x799 | 122.9 KB | 6 | Adapters (All sources), Landing, SignIn, etc. | Modern Study Desk with Laptop | Replaced with dynamic hash-based cover plates |

---

## 3. Motion & Interaction Deficiency Audit

1. **Landing Page:**
   - **Hero:** Static initial display without staggered sequence; mouse movement applied raw inline CSS properties without deceleration smoothing.
   - **Corridor Stream:** CSS infinite loop duplicated the same 3 images without interactive scrub or pause capability.
   - **Specimens:** Hover interaction was limited to a rigid opacity transition.
2. **Dashboard:**
   - Saved lesson counter (`lessons.length`) and material count (`sources.length`) rendered instantly without numerical interpolation.
   - Primary action cards lacked elevated hover feedback and tactile micro-interactions.
3. **Topic Explorer:**
   - Lacked visual subject category discovery; students were presented with a generic blank form.
4. **Learning Studio Workspace:**
   - **Visualize Tab:** Real DAG flowchart nodes and edges rendered instantaneously as raw HTML boxes without progressive edge reveal or connection highlighting.
   - **Practice Tab:** Radio button selection lacked responsive tactile feedback; score calculation appeared instantaneously without count-up animation.
   - **Ask AI Tab:** Answers rendered abruptly into the chat container without message reveal motion.
   - **Notes Tab:** Statically rendered without notebook-style tactile transitions.

---

## 4. Remediation & Visual Architecture Plan

- **Stage A:** Image diversity realignment (eliminate duplicate plates across Landing, TransformationSpecimen, HowItWorks, and Library adapters).
- **Stage B:** Unified Motion Architecture in `src/animations/` using GSAP 3.15 + Anime.js 4.5.
- **Stage C:** Cinematic Landing Hero entrance sequence & subtle architectural background motion.
- **Stage D:** Dashboard & Topic Explorer micro-interactions and animated live counters.
- **Stage E:** Learning Studio dynamic edge drawing and tactile pedagogical interactions.
- **Stage F:** Full cross-browser regression validation (`npm test`, `npm run test:e2e`, `npm run build`).
