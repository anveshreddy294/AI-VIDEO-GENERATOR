import { useEffect, useRef, useState } from 'react';
import { gsap, animateHeroEntrance, animateSectionReveal } from '../gsap/gsapCore';
import { animateCounter, animateTapFeedback, animateDiagramFlow } from '../anime/animeCore';
import { usePrefersReducedMotion } from '../accessibility/reducedMotion';

/**
 * Hook to manage scoped GSAP animations with automatic lifecycle cleanup.
 */
export function useGsapContext(buildFn, deps = [], scopeRef = null) {
  const localRef = useRef(null);
  const targetRef = scopeRef || localRef;

  useEffect(() => {
    if (!targetRef.current) return;
    const ctx = gsap.context(buildFn, targetRef.current);
    return () => ctx.revert();
  }, deps);

  return targetRef;
}

/**
 * Hook for Landing Page hero entrance sequence.
 */
export function useHeroEntrance(scopeRef, selectors = {}) {
  useEffect(() => {
    if (!scopeRef?.current) return;
    const ctx = animateHeroEntrance(scopeRef, selectors);
    return () => ctx?.revert();
  }, [scopeRef]);
}

/**
 * Hook for animated numerical metrics (e.g. lesson counts, quiz percentage).
 */
export function useAnimatedCounter(endValue, duration = 700) {
  const [displayValue, setDisplayValue] = useState(endValue);
  const prevValueRef = useRef(endValue);
  const prefersReduced = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReduced) {
      setDisplayValue(endValue);
      prevValueRef.current = endValue;
      return;
    }

    const start = prevValueRef.current;
    const anim = animateCounter(start, endValue, (val) => setDisplayValue(val), duration);
    prevValueRef.current = endValue;

    return () => {
      if (anim && typeof anim.cancel === 'function') {
        anim.cancel();
      }
    };
  }, [endValue, duration, prefersReduced]);

  return displayValue;
}

/**
 * Hook for diagram reveal in Visualize panel.
 */
export function useDiagramAnimation(containerRef, triggerDeps = []) {
  const prefersReduced = usePrefersReducedMotion();

  useEffect(() => {
    if (!containerRef?.current || prefersReduced) return;
    const timer = setTimeout(() => {
      animateDiagramFlow(containerRef.current);
    }, 60);

    return () => clearTimeout(timer);
  }, triggerDeps);
}
