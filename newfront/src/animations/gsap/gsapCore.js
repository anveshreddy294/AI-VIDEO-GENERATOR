import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { getPrefersReducedMotion } from '../accessibility/reducedMotion';
import { DURATIONS, EASINGS, STAGGERS } from '../presets/motionTokens';

// Register plugins once
if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger);
}

export { gsap, ScrollTrigger };

/**
 * Creates a scoped GSAP context with automatic React cleanup.
 */
export function createScopedGsap(scopeRef, buildFn) {
  if (!scopeRef || !scopeRef.current) return null;
  const ctx = gsap.context(buildFn, scopeRef.current);
  return ctx;
}

/**
 * Hero entrance sequence:
 * Staggers kicker, headline lines, lead paragraph, actions, and floating plates.
 */
export function animateHeroEntrance(scopeRef, selectors = {}) {
  if (!scopeRef?.current) return null;
  const reduced = getPrefersReducedMotion();

  const {
    kicker = '.hero-kicker-tag',
    headline = '.hero-editorial-headline',
    lead = '.hero-lead-text',
    actions = '.hero-actions-group',
    provenance = '.hero-provenance-strip',
    visualMount = '.floating-hero-plate',
    satellites = '.satellite-floating-plate',
    chips = '.hero-floating-chip',
    registration = '.hero-registration-line'
  } = selectors;

  return gsap.context(() => {
    if (reduced) {
      // Immediate reveal without motion
      gsap.set([kicker, headline, lead, actions, provenance, visualMount, satellites, chips, registration], {
        opacity: 1,
        y: 0,
        scale: 1,
        clearProps: 'all'
      });
      return;
    }

    const tl = gsap.timeline({
      defaults: { ease: EASINGS.gsapEditorial }
    });

    // 1. Technical Registration Line
    if (registration) {
      tl.fromTo(registration, 
        { opacity: 0, y: -8 }, 
        { opacity: 1, y: 0, duration: DURATIONS.fast }
      );
    }

    // 2. Proposition Kicker & Headline Stagger
    tl.fromTo(kicker,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: DURATIONS.fast },
      '-=0.1'
    )
    .fromTo(headline,
      { opacity: 0, y: 22 },
      { opacity: 1, y: 0, duration: DURATIONS.reveal, ease: 'power3.out' },
      '-=0.15'
    )
    .fromTo(lead,
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: DURATIONS.standard },
      '-=0.3'
    )
    .fromTo(actions,
      { opacity: 0, y: 14 },
      { opacity: 1, y: 0, duration: DURATIONS.standard },
      '-=0.25'
    );

    // 3. Provenance Strip
    if (provenance) {
      tl.fromTo(`${provenance} .prov-cell`,
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: DURATIONS.fast, stagger: STAGGERS.tight },
        '-=0.2'
      );
    }

    // 4. Central Visual Mount & Floating Satellites
    if (visualMount) {
      tl.fromTo(visualMount,
        { opacity: 0, scale: 0.96, y: 24 },
        { opacity: 1, scale: 1, y: 0, duration: DURATIONS.deliberate, ease: 'power2.out' },
        0.2
      );
    }

    if (satellites) {
      tl.fromTo(satellites,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: DURATIONS.reveal, stagger: STAGGERS.spacious, ease: 'power2.out' },
        0.4
      );
    }

    if (chips) {
      tl.fromTo(chips,
        { opacity: 0, scale: 0.92 },
        { opacity: 1, scale: 1, duration: DURATIONS.fast, stagger: STAGGERS.tight },
        0.6
      );
    }
  }, scopeRef.current);
}

/**
 * Scroll reveal for content sections.
 */
export function animateSectionReveal(element, targets = ':scope > *', options = {}) {
  if (!element) return null;
  const reduced = getPrefersReducedMotion();

  if (reduced) {
    gsap.set(element, { opacity: 1, y: 0, clearProps: 'all' });
    return null;
  }

  const {
    start = 'top 85%',
    y = 20,
    duration = DURATIONS.standard,
    stagger = STAGGERS.standard,
    scrub = false
  } = options;

  return ScrollTrigger.create({
    trigger: element,
    start,
    once: !scrub,
    onEnter: () => {
      gsap.fromTo(targets,
        { opacity: 0, y },
        { opacity: 1, y: 0, duration, stagger, ease: EASINGS.gsapEditorial }
      );
    }
  });
}

/**
 * Lightweight pointer parallax calculation.
 */
export function calculateParallax(pointerX, pointerY, maxShift = 12) {
  if (getPrefersReducedMotion()) return { x: 0, y: 0 };
  const clampedX = Math.max(-1, Math.min(1, pointerX));
  const clampedY = Math.max(-1, Math.min(1, pointerY));
  return {
    x: Math.round(clampedX * maxShift * 10) / 10,
    y: Math.round(clampedY * maxShift * 10) / 10
  };
}
