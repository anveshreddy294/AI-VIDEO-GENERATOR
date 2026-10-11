import { animate, createTimeline, stagger } from 'animejs';
import { getPrefersReducedMotion } from '../accessibility/reducedMotion';
import { DURATIONS } from '../presets/motionTokens';

/**
 * VisualAI — Anime.js v4 Motion Utilities
 * Specialized for SVG line drawing, micro-interactions, counters, and pulse states.
 */

/**
 * Animates a number from start to end smoothly.
 * Safe for student dashboard metrics and real assessment results.
 */
export function animateCounter(startValue, endValue, onUpdate, duration = 800) {
  if (getPrefersReducedMotion()) {
    onUpdate(endValue);
    return null;
  }

  const tracker = { value: startValue };
  return animate(tracker, {
    value: endValue,
    duration,
    ease: 'outQuad',
    onUpdate: () => {
      onUpdate(Math.round(tracker.value));
    }
  });
}

/**
 * Micro-interaction feedback for buttons and tabs.
 * Gives a crisp, architectural tactile snap without heavy bounce.
 */
export function animateTapFeedback(element) {
  if (!element || getPrefersReducedMotion()) return null;

  return animate(element, {
    scale: [1, 0.97, 1],
    duration: 180,
    ease: 'outQuad'
  });
}

/**
 * Animated SVG stroke reveal.
 * Used for concept flowchart edges, mathematical lines, and registration glyphs.
 */
export function animateSvgStroke(pathElement, options = {}) {
  if (!pathElement) return null;
  const reduced = getPrefersReducedMotion();

  const {
    duration = 750,
    delay = 0,
    strokeColor = '#A46047'
  } = options;

  if (reduced) {
    pathElement.style.strokeDashoffset = '0';
    return null;
  }

  // Calculate or set path length
  const length = pathElement.getTotalLength ? pathElement.getTotalLength() : 300;
  pathElement.style.strokeDasharray = `${length}`;
  pathElement.style.strokeDashoffset = `${length}`;

  return animate(pathElement, {
    strokeDashoffset: [length, 0],
    duration,
    delay,
    ease: 'inOutQuad'
  });
}

/**
 * Staggered entrance for diagram nodes and educational connection lines.
 */
export function animateDiagramFlow(containerElement) {
  if (!containerElement || getPrefersReducedMotion()) return null;

  const nodes = containerElement.querySelectorAll('.workspace-diagram-node');
  const edges = containerElement.querySelectorAll('.workspace-diagram-edge');

  const tl = createTimeline();

  if (nodes.length > 0) {
    tl.add(nodes, {
      opacity: [0, 1],
      translateY: [10, 0],
      duration: 380,
      delay: stagger(60),
      ease: 'outQuad'
    });
  }

  if (edges.length > 0) {
    tl.add(edges, {
      opacity: [0, 1],
      translateX: [-8, 0],
      duration: 320,
      delay: stagger(50),
      ease: 'outQuad'
    }, '-=150');
  }

  return tl;
}

/**
 * Subtle live beacon pulse (for "ACTIVE ENGINE" or "STUDENT WORKSPACE" status chips).
 */
export function animateBeaconPulse(dotElement) {
  if (!dotElement || getPrefersReducedMotion()) return null;

  return animate(dotElement, {
    scale: [1, 1.25, 1],
    opacity: [0.75, 1, 0.75],
    duration: 2200,
    loop: true,
    ease: 'inOutSine'
  });
}
