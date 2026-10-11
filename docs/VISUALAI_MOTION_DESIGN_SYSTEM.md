# VisualAI Knowledge Atelier — Motion Design System & Architectural Standards

**System Version:** 3.1.0  
**Libraries:** GSAP 3.15.0 + Anime.js 4.5.0  
**Aesthetic Core:** Archival Academic Typography, Non-Harsh Architectural Transitions, Compositor Performance  

---

## 1. Principles of Atelier Motion

1. **Pedagogical Purpose Over Decorative Spectacle**  
   Every animation exists to clarify information hierarchy, demonstrate causal relationships between scientific concepts, or provide immediate, tactile feedback for student interactions.
2. **Restrained Architectural Geometry**  
   No cartoonish rubber-banding, neon glows, or 3D tilt novelties. Easing mimics deliberate mechanical instruments: crisp starts and calibrated, smooth settling.
3. **Strict Separation of Concerns**  
   - **GSAP 3**: Orchestrates multi-element page timelines, staggered layout entrances, scroll-triggered section reveals, and view coordinate transitions.
   - **Anime.js 4**: Orchestrates SVG vector path drawing (`strokeDashoffset`), micro-interaction scale snaps, numerical metric interpolation (`value` counters), and live status pulses.
   - **Zero Collision Guarantee**: GSAP and Anime.js never manipulate identical CSS properties on the same DOM element concurrently.
4. **Absolute Accessibility & Reduced Motion Defense**  
   `prefers-reduced-motion: reduce` is unconditionally respected via central listeners. All critical content renders immediately in its final, readable state when reduced motion is requested.

---

## 2. Motion Tokens & Durations

All durations and easings are codified in `src/animations/presets/motionTokens.js`:

```javascript
export const DURATIONS = {
  instant: 0.1,       // Micro-feedback, instant toggle
  fast: 0.2,          // Button press, chip hover
  standard: 0.45,     // Card entrance, tab switch
  reveal: 0.65,       // Hero headline stagger, diagram edge drawing
  deliberate: 0.9,    // Stage transitions, specimen inspection
  atmospheric: 1.4    // Ambient orbital drift
};

export const EASINGS = {
  editorial: 'cubic-bezier(0.16, 1, 0.3, 1)',   // Fast entry, gradual architectural settle
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',  // Subtle tactile snap
  decelerate: 'cubic-bezier(0, 0, 0.2, 1)',     // Pure deceleration
  gsapEditorial: 'power2.out',
  gsapSmooth: 'power3.out'
};
```

---

## 3. Five Motion Patterns

### Pattern A: Reveal Motion (GSAP 3)
Used for page headers, hero propositions, and multi-column specimen galleries.
- Staggers elements by 40ms–80ms.
- Translates `y: 12px -> 0px` and `opacity: 0 -> 1` on the GPU compositor thread.
- Avoids animating `height`, `margin`, or `top`.

### Pattern B: Ambient Motion (CSS / Hardware Accelerated SVG)
Background subtle grid coordinates and constellation orbits.
- Rendered with `pointer-events: none` and faint opacity (`0.04` to `0.08`).
- Pauses automatically during active video playback or assessment completion.

### Pattern C: Interaction Motion (Anime.js 4)
Micro-feedback on primary actions and study cards.
- Subtle scale compression: `scale: [1, 0.97, 1]` over 180ms.
- Clear visual active border shift using Terracotta (`#A46047`).

### Pattern D: Educational Motion (Anime.js 4)
Concept graph drawing and numerical evaluation results.
- Flowchart edges animate `strokeDashoffset` from path length to 0.
- Nodes stagger in top-to-bottom according to topological ordering.
- Practice assessment score interpolates smoothly from 0 to actual backend percentage.

### Pattern E: Transition Motion
Tab switching between the canonical 6 lesson workspaces (`Learn`, `Notes`, `Visualize`, `Practice`, `Ask AI`, `Video`).
- Zero tab latency; immediate state switch with 180ms smooth panel fade-in.
- Strictly avoids re-triggering backend inference or mutating active lesson identity.
