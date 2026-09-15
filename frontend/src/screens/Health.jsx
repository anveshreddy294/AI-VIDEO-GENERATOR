import { useEffect, useState } from 'react';

export default function Health() {
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/health');
      if (response.ok) {
        const data = await response.json();
        setHealthData(data);
      } else {
        throw new Error('API server returned error code ' + response.status);
      }
    } catch (err) {
      setError(err.message || 'Failed to contact local API server diagnostics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: 'var(--space-8)' }}>
      
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-8)', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <h1 className="serif-title" style={{ fontSize: '38px', fontWeight: '400', color: 'var(--text-primary)' }}>
            System Diagnostics
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Real-time checking status for textbook indexing structures, active renderers, and AI models.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={loading}
          className="btn btn-ghost"
          style={{ fontSize: '13px', padding: '8px 16px' }}
        >
          {loading ? 'Diagnosing...' : 'Refresh Status'}
        </button>
      </div>

      {loading ? (
        <div style={{ padding: 'var(--space-10) 0', color: 'var(--text-secondary)', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span>⏳ Running subprocess diagnostics...</span>
        </div>
      ) : error ? (
        <div
          style={{
            background: 'rgba(244, 63, 94, 0.06)',
            border: '1px solid var(--accent-rose)',
            borderRadius: 'var(--r-lg)',
            padding: 'var(--space-6)',
            color: 'var(--text-primary)'
          }}
        >
          <h3 style={{ margin: '0 0 10px 0', fontSize: '16px' }}>API Server Offline</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
            {error} Make sure that the backend Express server is running on port 5000.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '760px' }}>
          
          {/* Overall status badge */}
          <div
            style={{
              background: healthData.ok ? 'rgba(20, 184, 166, 0.05)' : 'rgba(245, 158, 11, 0.05)',
              border: healthData.ok ? '1px solid var(--accent-teal)' : '1px solid var(--accent-amber)',
              borderRadius: 'var(--r-md)',
              padding: 'var(--space-4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Workspace Status</span>
              <h3 style={{ fontSize: '20px', color: 'var(--text-primary)', margin: '2px 0 0 0' }}>
                {healthData.ok ? 'All systems nominal' : 'Some non-essential components inactive'}
              </h3>
            </div>
            <span style={{ fontSize: '32px' }}>{healthData.ok ? '🟢' : '🟡'}</span>
          </div>

          {/* Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            
            {/* 1. Ollama */}
            <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Ollama Local LLM</span>
                <span style={{ fontSize: '12px' }}>{healthData.services.ollama.ok ? '🟢' : '⚪'}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                {healthData.services.ollama.message}
              </p>
            </div>

            {/* 2. Gemini API */}
            <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Gemini Flash API</span>
                <span style={{ fontSize: '12px' }}>{healthData.services.gemini.ok ? '🟢' : '⚪'}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                {healthData.services.gemini.message}
              </p>
            </div>

            {/* 3. Manim Compiler */}
            <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Manim Compiler</span>
                <span style={{ fontSize: '12px' }}>{healthData.services.manim.ok ? '🟢' : '🔴'}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                {healthData.services.manim.message}
              </p>
            </div>

            {/* 4. FFmpeg assembly */}
            <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>FFmpeg Video Muxer</span>
                <span style={{ fontSize: '12px' }}>{healthData.services.ffmpeg.ok ? '🟢' : '🔴'}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                {healthData.services.ffmpeg.message}
              </p>
            </div>

            {/* 5. Piper TTS */}
            <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Piper TTS Narrator</span>
                <span style={{ fontSize: '12px' }}>{healthData.services.piper.ok ? '🟢' : '🟡'}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                {healthData.services.piper.message}
              </p>
            </div>

          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Last checked timestamp: {new Date(healthData.timestamp).toLocaleString()}
          </div>

        </div>
      )}

    </div>
  );
}
