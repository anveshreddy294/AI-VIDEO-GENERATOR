import { useEffect, useRef, useState } from 'react';

// Generates fallback timed transcript items if none are supplied in session
function generateDefaultTranscript(scenePlan) {
  if (!scenePlan || scenePlan.length === 0) {
    return [
      { start: 0, end: 8, text: "Welcome to this specialized learning module. We are going to explore this textbook section in depth, visualising every dynamic force and relationship step-by-step." },
      { start: 8, end: 16, text: "Let's first observe how the baseline values are defined. Notice the initial stable equilibrium in the system before external influences are introduced." },
      { start: 16, end: 24, text: "Now, as we shift the key variables, the displacement curve reveals a steady adjustment. This corresponds to the derivative formulas grounding our concept." },
      { start: 24, end: 35, text: "In conclusion, the balance of these active elements explains the core physical behavior. Take a moment to review this timeline before moving on to the exercises." }
    ];
  }

  let accTime = 0;
  return scenePlan.map((scene, idx) => {
    const duration = scene.duration_seconds || 10;
    const start = accTime;
    const end = accTime + duration;
    accTime += duration;

    // Use scene description or plan as text
    return {
      start,
      end,
      text: scene.description || `Scene ${idx + 1} renders. Exploring ${scene.title || 'the core subject concept'} using visual transformations and synchronized audio overlays.`
    };
  });
}

export default function TranscriptPanel({ currentTime = 0, scenePlan = null, isPipelineRunning = false }) {
  const containerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const segments = generateDefaultTranscript(scenePlan);

  useEffect(() => {
    if (!autoScroll || isPipelineRunning) return;
    
    // Find active element
    const activeEl = containerRef.current?.querySelector('.active-segment');
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentTime, autoScroll, isPipelineRunning]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden'
      }}
    >
      {/* Header Panel */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-overlay)'
        }}
      >
        <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-primary)' }}>Narration Transcript</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              style={{ accentColor: 'var(--accent-amber)' }}
            />
            Auto-Sync
          </label>
        </div>
      </div>

      {/* Script Lines Scroll Container */}
      <div
        ref={containerRef}
        className="custom-scrollbar"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 'var(--space-4)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)'
        }}
      >
        {isPipelineRunning ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
              gap: '10px',
              color: 'var(--text-muted)',
              fontSize: '12px'
            }}
          >
            <span>⏳ Awaiting pipeline assembly...</span>
          </div>
        ) : (
          segments.map((seg, idx) => {
            const isActive = currentTime >= seg.start && currentTime < seg.end;
            return (
              <div
                key={idx}
                className={isActive ? 'active-segment' : ''}
                style={{
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--r-md)',
                  background: isActive ? 'rgba(245, 158, 11, 0.04)' : 'transparent',
                  borderLeft: isActive ? '2px solid var(--accent-amber)' : '2px solid transparent',
                  transition: 'all 0.3s ease',
                  cursor: 'pointer'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span
                    className="mono-text"
                    style={{
                      fontSize: '10px',
                      color: isActive ? 'var(--accent-amber)' : 'var(--text-muted)'
                    }}
                  >
                    Scene {idx + 1}
                  </span>
                  <span
                    className="mono-text"
                    style={{
                      fontSize: '10px',
                      color: 'var(--text-muted)'
                    }}
                  >
                    {Math.floor(seg.start)}s - {Math.floor(seg.end)}s
                  </span>
                </div>
                <p
                  style={{
                    fontSize: '13px',
                    lineHeight: '1.5',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                    margin: 0
                  }}
                >
                  {seg.text}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
