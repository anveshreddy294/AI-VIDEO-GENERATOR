import React, { useEffect, useRef } from 'react';

/**
 * AtelierFloatingCanvas
 * Renders an ethereal, ultra-restrained architectural particle field in zero-gravity.
 * Uses mathematical coordinate marks (+, ·, ⊞, λ, ∂, [x,y]) in warm ink tones.
 * Strictly adheres to 0-4px radius, no drop shadows, no radial orbs, no harsh gradients.
 */
export default function AtelierFloatingCanvas({ className = '' }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };

    window.addEventListener('resize', handleResize);

    // Architectural glyphs and coordinate markers
    const GLYPHS = ['+', '·', '⊞', '×', 'λ', '∂', 'Δ', '142', '288', '37°N', '∫', 'dτ', '§'];

    const PARTICLE_COUNT = 28;
    const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vy: -(0.25 + Math.random() * 0.45), // gentle upward float
      vx: (Math.random() - 0.5) * 0.2,
      baseX: Math.random() * width,
      amplitude: 15 + Math.random() * 25,
      frequency: 0.0008 + Math.random() * 0.0012,
      phase: Math.random() * Math.PI * 2,
      glyph: GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
      opacity: 0.08 + Math.random() * 0.14,
      size: 9 + Math.floor(Math.random() * 4),
      time: Math.random() * 1000
    }));

    let lastTime = performance.now();

    const render = (now) => {
      const dt = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;

      ctx.clearRect(0, 0, width, height);

      ctx.font = '10px "IBM Plex Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.time += dt * 1000;
        p.y += p.vy;
        p.x = p.baseX + Math.sin(p.time * p.frequency + p.phase) * p.amplitude;

        // Wrap around top to bottom
        if (p.y < -20) {
          p.y = height + 20;
          p.baseX = Math.random() * width;
          p.x = p.baseX;
        }

        // Draw particle in architectural ink
        ctx.fillStyle = `rgba(28, 27, 25, ${p.opacity})`;
        ctx.fillText(p.glyph, p.x, p.y);
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef} 
      className={`atelier-floating-canvas ${className}`}
      aria-hidden="true"
    />
  );
}
