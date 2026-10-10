import React from 'react';

/**
 * VISUALAI : BESPOKE ATELIER GLYPHS
 * 100% Original Architectural & Scientific SVG Icons
 * Strictly Zero Lucide, Zero Emojis, Zero Sparkles, Zero Animated Arrows
 */

export function GlyphBrandMark({ size = 20, className = '' }) {
  return (
    <svg width={size} height={(size * 22) / 26} viewBox="0 0 26 22" fill="none" className={className} aria-hidden="true">
      <path d="M2 3L13 19L24 3" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" strokeLinejoin="miter" />
      <path d="M6.5 3L13 13.5L19.5 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" strokeLinejoin="miter" />
      <line x1="2" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphDocument({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect x="2.5" y="1.5" width="11" height="13" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5" y1="5" x2="11" y2="5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5" y1="11" x2="9" y2="11" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphEvidence({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect x="2" y="2" width="12" height="12" stroke="currentColor" strokeWidth="1.2" strokeDasharray="2 2" />
      <circle cx="8" cy="8" r="2.5" fill="currentColor" />
      <line x1="8" y1="2" x2="8" y2="4" stroke="currentColor" strokeWidth="1.2" />
      <line x1="8" y1="12" x2="8" y2="14" stroke="currentColor" strokeWidth="1.2" />
      <line x1="2" y1="8" x2="4" y2="8" stroke="currentColor" strokeWidth="1.2" />
      <line x1="12" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphDag({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <circle cx="3.5" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="12.5" cy="4" r="2" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="12.5" cy="12" r="2" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5.5" y1="7" x2="10.5" y2="4.8" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5.5" y1="9" x2="10.5" y2="11.2" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphCheckmark({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className} aria-hidden="true">
      <path d="M2.5 7.5L5.5 10.5L11.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="square" />
    </svg>
  );
}

export function GlyphArrowRight({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className} aria-hidden="true">
      <line x1="2" y1="7" x2="11.5" y2="7" stroke="currentColor" strokeWidth="1.3" />
      <polyline points="8,3.5 11.5,7 8,10.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="square" />
    </svg>
  );
}

export function GlyphArrowUpRight({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className} aria-hidden="true">
      <line x1="3.5" y1="10.5" x2="10.5" y2="3.5" stroke="currentColor" strokeWidth="1.3" />
      <polyline points="5.5,3.5 10.5,3.5 10.5,8.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="square" />
    </svg>
  );
}

export function GlyphSearch({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" />
    </svg>
  );
}

export function GlyphPlay({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className} aria-hidden="true">
      <polygon points="4,2.5 11.5,7 4,11.5" fill="currentColor" />
    </svg>
  );
}

export function GlyphPause({ size = 14, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={className} aria-hidden="true">
      <rect x="3.5" y="2.5" width="2.5" height="9" fill="currentColor" />
      <rect x="8" y="2.5" width="2.5" height="9" fill="currentColor" />
    </svg>
  );
}

export function GlyphCrosshair({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="8" y1="1" x2="8" y2="4" stroke="currentColor" strokeWidth="1.2" />
      <line x1="8" y1="12" x2="8" y2="15" stroke="currentColor" strokeWidth="1.2" />
      <line x1="1" y1="8" x2="4" y2="8" stroke="currentColor" strokeWidth="1.2" />
      <line x1="12" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphLayers({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <polygon points="8,1.5 14.5,5 8,8.5 1.5,5" stroke="currentColor" strokeWidth="1.2" />
      <polyline points="2.5,8 8,11 13.5,8" stroke="currentColor" strokeWidth="1.2" />
      <polyline points="2.5,11 8,14 13.5,11" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphTerminal({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect x="2" y="2" width="12" height="12" stroke="currentColor" strokeWidth="1.2" />
      <polyline points="4.5,6 7,8 4.5,10" stroke="currentColor" strokeWidth="1.2" />
      <line x1="8.5" y1="10" x2="11.5" y2="10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphUser({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.2" />
      <path d="M2.5 14C2.5 11.2 5 9.5 8 9.5C11 9.5 13.5 11.2 13.5 14" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphRotate({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <path d="M13.5 8C13.5 11 11 13.5 8 13.5C5 13.5 2.5 11 2.5 8C2.5 5 5 2.5 8 2.5C10.5 2.5 12.5 4 13.2 6.2" stroke="currentColor" strokeWidth="1.2" />
      <polyline points="10.5,6.5 13.5,6.5 13.5,3.5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function GlyphGrid({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect x="2" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="9" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="2" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="9" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}
