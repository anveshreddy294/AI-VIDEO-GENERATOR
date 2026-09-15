import { useEffect, useRef } from 'react';

export default function Landing({ onStart }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;

    // Set canvas dimensions
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Particle settings
    const particles = [];
    const particleCount = 65;
    const connectionDistance = 120;

    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2 + 1
      });
    }

    // Animation Loop
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw and update particles
      particles.forEach((p, idx) => {
        p.x += p.vx;
        p.y += p.vy;

        // Bounce on borders
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(240, 239, 232, 0.2)';
        ctx.fill();

        // Connect lines
        for (let j = idx + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < connectionDistance) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            const alpha = (1 - dist / connectionDistance) * 0.15;
            ctx.strokeStyle = `rgba(240, 239, 232, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      });

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div
      style={{
        position: 'relative',
        width: '100vw',
        height: '100vh',
        background: 'var(--bg-base)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '0 2rem',
        overflow: 'hidden'
      }}
    >
      {/* Background Interactive Particle Canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 1
        }}
      />

      {/* Hero Cinematic Elements */}
      <div
        style={{
          position: 'relative',
          zIndex: 2,
          maxWidth: '800px',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 'var(--space-6)'
        }}
      >
        <span
          className="mono-text"
          style={{
            fontSize: '11px',
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            color: 'var(--accent-amber)',
            background: 'rgba(245,158,11,0.06)',
            padding: '4px 12px',
            borderRadius: '100px',
            border: '1px solid var(--accent-amber-dim)'
          }}
        >
          Frontend Specification · v1.0 · RAG_MANIM Pipeline
        </span>

        <h1
          className="serif-title"
          style={{
            fontSize: 'clamp(48px, 6vw, 76px)',
            lineHeight: '1.05',
            color: 'var(--text-primary)',
            margin: 0
          }}
        >
          Learn anything. <br />
          <em style={{ color: 'var(--accent-blue)', fontStyle: 'italic' }}>Deeply.</em>
        </h1>

        <p
          style={{
            fontSize: 'clamp(16px, 2.5vw, 19px)',
            color: 'var(--text-secondary)',
            fontWeight: 300,
            maxWidth: '560px',
            lineHeight: '1.6',
            margin: '0 auto'
          }}
        >
          The AI-native educational operating system that converts your textbook sections into high-quality, personalized animated lessons.
        </p>

        {/* Action Button Strip */}
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', justifyContent: 'center', marginTop: 'var(--space-2)' }}>
          <button onClick={onStart} className="btn btn-primary" style={{ fontSize: '15px', padding: '14px 28px' }}>
            Start Learning →
          </button>
          <a href="#how-it-works" className="btn btn-ghost" style={{ fontSize: '15px', padding: '14px 28px' }}>
            See how it works
          </a>
        </div>

        {/* Demo Sub-Pills */}
        <div
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            alignItems: 'center',
            marginTop: 'var(--space-8)',
            fontSize: '13px',
            color: 'var(--text-secondary)'
          }}
        >
          <span>Available subjects:</span>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <span className="badge badge-blue">Physics</span>
            <span className="badge badge-teal">Chemistry</span>
            <span className="badge badge-violet">Mathematics</span>
            <span className="badge badge-rose">Biology</span>
          </div>
        </div>
      </div>
    </div>
  );
}
