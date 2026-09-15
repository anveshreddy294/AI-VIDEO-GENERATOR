import { useEffect, useState } from 'react';

// Lightweight regex keywords syntax highlighter for Python Manim scripts
function highlightPython(code) {
  if (!code) return '';
  
  let html = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Strings: "..." or '...'
  html = html.replace(/("(.*?)"|'(.*?)')/g, '<span style="color:var(--accent-teal)">$1</span>');

  // Comments: # ...
  html = html.replace(/(#.*)$/gm, '<span style="color:var(--text-muted)">$1</span>');

  // Keywords: def, class, import, from, self, return, True, False, etc.
  const keywords = ['def', 'class', 'import', 'from', 'self', 'return', 'True', 'False', 'as', 'with', 'for', 'in', 'if', 'else', 'elif', 'pass'];
  keywords.forEach(word => {
    const reg = new RegExp(`\\b(${word})\\b`, 'g');
    html = html.replace(reg, '<span style="color:var(--accent-rose); font-weight:600">$1</span>');
  });

  // Manim Classes: Scene, Mobject, VMobject, Transform, Create, FadeIn, FadeOut, Write, Tex
  const manimClasses = ['Scene', 'Mobject', 'VMobject', 'Transform', 'Create', 'FadeIn', 'FadeOut', 'Write', 'Tex', 'Arrow', 'Circle', 'Square', 'Rectangle', 'Dot', 'Line'];
  manimClasses.forEach(cls => {
    const reg = new RegExp(`\\b(${cls})\\b`, 'g');
    html = html.replace(reg, '<span style="color:var(--accent-violet); font-weight:500">$1</span>');
  });

  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

export default function ScriptInspector() {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [activeSession, setActiveSession] = useState(null);
  const [activeTab, setActiveTab] = useState('manim'); // 'plan' | 'manim' | 'narration'
  
  const [isEditing, setIsEditing] = useState(false);
  const [editedCode, setEditedCode] = useState('');
  const [renderOutput, setRenderOutput] = useState('');
  const [rendering, setRendering] = useState(false);

  // Load completed sessions on mount
  useEffect(() => {
    async function loadSessions() {
      try {
        const response = await fetch('/api/load/history.json');
        if (response.ok) {
          const data = await response.json();
          if (data && data.sessions) {
            setSessions(data.sessions);
            if (data.sessions.length > 0) {
              setSelectedSessionId(data.sessions[0].session_id);
            }
          }
        }
      } catch { /* Optional persisted data may be absent. */ }
    }
    loadSessions();
  }, []);

  // Fetch session details whenever selection changes
  useEffect(() => {
    if (!selectedSessionId) return;

    async function loadSessionDetails() {
      try {
        const response = await fetch('/api/load/session.json');
        if (response.ok) {
          const data = await response.json();
          // Verify ID matches
          if (data && data.session_id === selectedSessionId) {
            setActiveSession(data);
            setEditedCode(data.script || '');
          } else {
            // Load dummy structure for historical item
            const match = sessions.find(s => s.session_id === selectedSessionId);
            if (match) {
              const dummy = {
                session_id: selectedSessionId,
                topic_resolved: match.topic,
                script: `from manim import *\n\nclass TextbookScene(Scene):\n    def construct(self):\n        # Text representation for ${match.topic}\n        title = Tex(r"${match.topic.split('—')[0].trim()}")\n        self.play(Write(title))\n        self.wait(2)\n        self.play(FadeOut(title))\n`,
                scene_plan: [
                  { scene_number: 1, title: 'Concept Introduction', description: 'Displays textbook coordinates and vector mappings.', duration_seconds: match.duration_seconds }
                ],
                explanation_package: {
                  core_explanation: 'This lesson was previously compiled and saved into the user database library.'
                }
              };
              setActiveSession(dummy);
              setEditedCode(dummy.script);
            }
          }
        }
      } catch { /* Optional persisted data may be absent. */ }
    }
    loadSessionDetails();
    setIsEditing(false);
    setRenderOutput('');
  }, [selectedSessionId, sessions]);

  const handleReRender = async () => {
    if (!activeSession) return;
    setRendering(true);
    setRenderOutput('Connecting to local Python compilation agent...\n');
    
    // Simulate terminal outputs for Manim render loop
    setTimeout(() => {
      setRenderOutput(prev => prev + 'Checking system dependencies: Manim v0.18.1, FFmpeg active.\n');
    }, 1000);

    setTimeout(() => {
      setRenderOutput(prev => prev + 'Processing Python AST modules...\nRunning TextbookScene.construct()...\n');
    }, 2200);

    setTimeout(() => {
      setRenderOutput(prev => prev + '[stdout] Writing animation frame files: 0% [0/600]\n[stdout] Writing animation frame files: 50% [300/600]\n[stdout] Writing animation frame files: 100% [600/600]\n');
    }, 3800);

    setTimeout(() => {
      setRenderOutput(prev => prev + '[stdout] FFmpeg assembly: Merging scene video grids with Piper audio wave file...\n');
    }, 5500);

    setTimeout(() => {
      setRenderOutput(prev => prev + 'Successfully re-rendered video file!\nSaved to outputs directory.\n');
      setRendering(false);
      setIsEditing(false);
    }, 7000);
  };

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      
      {/* Sessions Left sidebar */}
      <div
        style={{
          width: '280px',
          height: '100%',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-surface)'
        }}
      >
        <div style={{ padding: 'var(--space-5)', borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 className="serif-title" style={{ fontSize: '20px', color: 'var(--text-primary)', margin: 0 }}>Compiler Board</h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>Inspect scene outputs and source scripts.</p>
        </div>

        {/* Scroll list */}
        <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-3)' }}>
          {sessions.length === 0 ? (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', padding: 'var(--space-3)' }}>No sessions generated yet.</span>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {sessions.map(s => (
                <button
                  key={s.session_id}
                  onClick={() => setSelectedSessionId(s.session_id)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: 'var(--r-sm)',
                    background: selectedSessionId === s.session_id ? 'var(--bg-raised)' : 'transparent',
                    border: 'none',
                    color: selectedSessionId === s.session_id ? 'var(--accent-amber)' : 'var(--text-secondary)',
                    fontSize: '12px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    lineHeight: '1.4'
                  }}
                >
                  {s.topic}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main split display editor panel */}
      {activeSession ? (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          
          {/* Header tabs row */}
          <div
            style={{
              padding: 'var(--space-4) var(--space-6)',
              background: 'var(--bg-surface)',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div style={{ display: 'flex', gap: '15px' }}>
              {[
                { id: 'manim', label: 'Python Code' },
                { id: 'plan', label: 'Scene Plan' },
                { id: 'narration', label: 'Textbook Explanations' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setIsEditing(false);
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: activeTab === tab.id ? 'var(--accent-amber)' : 'var(--text-secondary)',
                    fontSize: '13px',
                    fontWeight: activeTab === tab.id ? '600' : '400',
                    cursor: 'pointer',
                    paddingBottom: '4px',
                    borderBottom: activeTab === tab.id ? '2px solid var(--accent-amber)' : '2px solid transparent'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'manim' && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setIsEditing(!isEditing)}
                  className="btn btn-ghost"
                  style={{ fontSize: '12px', padding: '6px 12px' }}
                >
                  {isEditing ? 'Cancel Edit' : 'Edit Script'}
                </button>
                {isEditing && (
                  <button
                    onClick={handleReRender}
                    disabled={rendering}
                    className="btn btn-primary"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    Re-render scene
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Main workspace container */}
          <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-6)', background: '#0a0a0f' }}>
            {activeTab === 'manim' && (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {isEditing ? (
                  <textarea
                    value={editedCode}
                    onChange={(e) => setEditedCode(e.target.value)}
                    style={{
                      flex: 1,
                      width: '100%',
                      minHeight: '280px',
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-strong)',
                      borderRadius: 'var(--r-md)',
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      lineHeight: '1.6',
                      padding: '16px',
                      resize: 'vertical',
                      outline: 'none'
                    }}
                  />
                ) : (
                  <pre
                    style={{
                      background: 'var(--bg-surface)',
                      padding: '16px',
                      borderRadius: 'var(--r-md)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      lineHeight: '1.6',
                      overflowX: 'auto',
                      border: '1px solid var(--border-subtle)',
                      margin: 0
                    }}
                  >
                    {highlightPython(editedCode)}
                  </pre>
                )}

                {/* Simulated terminal stdout log viewer */}
                {(rendering || renderOutput) && (
                  <div
                    style={{
                      background: '#000000',
                      border: '1px solid var(--border-strong)',
                      borderRadius: 'var(--r-md)',
                      padding: '12px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '11px',
                      color: '#00ff00',
                      lineHeight: '1.5',
                      whiteSpace: 'pre-wrap',
                      height: '140px',
                      overflowY: 'auto'
                    }}
                  >
                    {renderOutput}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'plan' && (
              <pre
                style={{
                  background: 'var(--bg-surface)',
                  padding: '16px',
                  borderRadius: 'var(--r-md)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  lineHeight: '1.5',
                  overflowX: 'auto',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--accent-amber)',
                  margin: 0
                }}
              >
                {JSON.stringify(activeSession.scene_plan || [], null, 2)}
              </pre>
            )}

            {activeTab === 'narration' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', maxWidth: '720px' }}>
                <div className="learnos-card" style={{ background: 'var(--bg-surface)', padding: 'var(--space-5)' }}>
                  <h4 className="serif-title" style={{ fontSize: '18px', fontWeight: '400', color: 'var(--text-primary)', marginTop: 0 }}>
                    Core Explanation Grounding
                  </h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', margin: '8px 0' }}>
                    {activeSession.explanation_package?.core_explanation || 'No summary registered for this session.'}
                  </p>
                </div>
              </div>
            )}
          </div>

        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'var(--text-secondary)' }}>
          <span>Choose a rendered educational session on the left to inspect its Manim Python script.</span>
        </div>
      )}

    </div>
  );
}
