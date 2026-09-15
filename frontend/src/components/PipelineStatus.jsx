
const STAGES = [
  { id: 'retrieving', label: 'Topic Retrieval', desc: 'Bootstraps the classroom agent and explanation package.' },
  { id: 'explaining', label: 'Educational Structuring', desc: 'Builds learning objectives, prerequisites, and analogies.' },
  { id: 'planning', label: 'Visual Scene Planning', desc: 'Storyboard + semantic plans from the concept guide (ideas.md).' },
  { id: 'generating', label: 'Manim Code Compilation', desc: 'Template or dynamic LLM scenes compiled and rendered.' },
  { id: 'tts', label: 'Narration & Audio Sync', desc: 'Piper TTS, WhisperX alignment, and FFmpeg merge.' }
];

export default function PipelineStatus({ currentStage, message, progress }) {
  const getStageStatus = (stageId) => {
    const stageOrder = ['idle', 'retrieving', 'explaining', 'planning', 'generating', 'tts', 'complete'];
    const currentIdx = stageOrder.indexOf(currentStage);
    const targetIdx = stageOrder.indexOf(stageId);

    if (currentStage === 'error') return 'error';
    if (currentStage === 'complete' || currentIdx > targetIdx) return 'complete';
    if (currentIdx === targetIdx) return 'active';
    return 'pending';
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-6)',
        padding: 'var(--space-6)',
        background: 'var(--bg-surface)',
        borderRadius: 'var(--r-lg)',
        border: '1px solid var(--border-default)',
        maxWidth: '560px',
        width: '100%',
        margin: '20px auto'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="serif-title" style={{ fontSize: '20px', fontWeight: '400' }}>
          Generating Lesson Animation
        </h3>
        <span className="mono-text" style={{ fontSize: '13px', color: 'var(--accent-amber)' }}>
          {progress}%
        </span>
      </div>

      {/* Main Progress Tracker Bar */}
      <div style={{ width: '100%', height: '6px', background: 'var(--bg-overlay)', borderRadius: '3px', overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${progress}%`,
            background: 'var(--accent-amber)',
            transition: 'width 0.4s ease',
            boxShadow: '0 0 8px var(--accent-amber)'
          }}
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginTop: '10px' }}>
        {STAGES.map(st => {
          const status = getStageStatus(st.id);
          return (
            <div key={st.id} style={{ display: 'flex', gap: 'var(--space-4)', opacity: status === 'pending' ? 0.4 : 1, transition: 'all 0.3s' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '11px',
                    background: status === 'complete' ? 'var(--accent-teal)' : status === 'active' ? 'var(--accent-blue-dim)' : 'var(--bg-overlay)',
                    border: status === 'active' ? '1px solid var(--accent-blue)' : '1px solid var(--border-default)',
                    color: status === 'complete' ? 'var(--text-inverted)' : status === 'active' ? 'var(--accent-blue)' : 'var(--text-muted)'
                  }}
                >
                  {status === 'complete' ? '✓' : status === 'active' ? '⟳' : '○'}
                </div>
                <div style={{ width: '1px', flex: 1, background: 'var(--border-subtle)', minHeight: '12px', margin: '4px 0' }} />
              </div>
              <div>
                <h4 style={{ fontSize: '13px', color: status === 'active' ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                  {st.label}
                </h4>
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                  {st.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-2)' }}>
        <span style={{ fontSize: '12px', color: 'var(--accent-rose)' }}>🤖 Pipeline Status:</span>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{message || 'Ready'}</span>
      </div>
    </div>
  );
}
