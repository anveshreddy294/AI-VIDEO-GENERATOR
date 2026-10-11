/**
 * VisualAI — The Knowledge Atelier
 * Motion Design System Tokens & Presets
 *
 * Grounded in the architectural editorial aesthetic:
 * restrained, crisp, non-distracting, purposeful.
 */

export const DURATIONS = {
  instant: 0.1,
  fast: 0.2,
  standard: 0.45,
  reveal: 0.65,
  deliberate: 0.9,
  atmospheric: 1.4,
};

export const EASINGS = {
  // Editorial smooth entry (fast start, gradual architectural settling)
  editorial: 'cubic-bezier(0.16, 1, 0.3, 1)',
  // Natural micro-interaction bounce
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  // Linear for ambient drift
  linear: 'linear',
  // Smooth deceleration for reveals
  decelerate: 'cubic-bezier(0, 0, 0.2, 1)',
  // GSAP ease equivalents
  gsapEditorial: 'power2.out',
  gsapSmooth: 'power3.out',
  gsapExpo: 'expo.out',
};

export const STAGGERS = {
  tight: 0.04,
  standard: 0.08,
  spacious: 0.14,
};
