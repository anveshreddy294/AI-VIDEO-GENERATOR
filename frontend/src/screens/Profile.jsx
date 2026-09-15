import { useState } from 'react';
import { useProfile } from '../context/ProfileContext';

export default function Profile() {
  const { profile, updateProfile, resetProfile } = useProfile();
  
  const [name, setName] = useState(profile.name || '');
  const [academicLevel, setAcademicLevel] = useState(profile.academic_level || 'class_11');
  const [examTargets, setExamTargets] = useState(profile.exam_target || []);
  const [learningStyle, setLearningStyle] = useState(profile.learning_style || 'visual');
  const [pace, setPace] = useState(profile.pace_preference || 'balanced');
  const [geminiApiKey, setGeminiApiKey] = useState(localStorage.getItem('GEMINI_API_KEY') || '');
  const [nvidiaApiKey, setNvidiaApiKey] = useState(localStorage.getItem('NVIDIA_API_KEY') || '');
  
  const [confidence, setConfidence] = useState({
    Chemistry: profile.confidence_map?.Chemistry || 50,
    Physics: profile.confidence_map?.Physics || 50,
    Mathematics: profile.confidence_map?.Mathematics || 50
  });

  const [message, setMessage] = useState('');

  const handleCheckboxChange = (target) => {
    if (examTargets.includes(target)) {
      setExamTargets(examTargets.filter(t => t !== target));
    } else {
      setExamTargets([...examTargets, target]);
    }
  };

  const handleConfidenceChange = (subject, val) => {
    setConfidence(prev => ({
      ...prev,
      [subject]: parseInt(val)
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      await updateProfile({
        name,
        academic_level: academicLevel,
        exam_target: examTargets,
        learning_style: learningStyle,
        pace_preference: pace,
        confidence_map: confidence
      });
      localStorage.setItem('GEMINI_API_KEY', geminiApiKey);
      localStorage.setItem('NVIDIA_API_KEY', nvidiaApiKey);
      localStorage.setItem('GROQ_API_KEY', geminiApiKey || nvidiaApiKey);
      setMessage('Profile settings saved and synchronised with prompt context!');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      console.error(err);
      setMessage('Failed to save profile settings.');
    }
  };

  const handleResetData = async () => {
    if (confirm('Are you sure you want to reset all profile data, learning history, and analytics? This cannot be undone.')) {
      await resetProfile();
      window.location.reload();
    }
  };

  const handleExportData = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(profile, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href",     dataStr);
    downloadAnchor.setAttribute("download", "learnos_profile.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: 'var(--space-8)' }}>
      
      {/* Page Title */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 className="serif-title" style={{ fontSize: '38px', fontWeight: '400', color: 'var(--text-primary)' }}>
          Learner Profile & Settings
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
          Customize your study preferences. LearnOS adjusts the multi-agent narrative explanations based on these parameters.
        </p>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: '800px' }}>
        
        {/* Core Identity Panel */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
          <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-amber)', marginBottom: 'var(--space-4)', marginTop: 0 }}>
            1. Identity & Targets
          </h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Learner Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--r-md)',
                  padding: '8px 12px',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Academic Level</label>
              <select
                value={academicLevel}
                onChange={(e) => setAcademicLevel(e.target.value)}
                style={{
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-default)',
                  color: 'var(--text-primary)',
                  borderRadius: 'var(--r-md)',
                  padding: '8px 12px',
                  fontSize: '13px',
                  outline: 'none'
                }}
              >
                <option value="class_9">Class 9 (High School)</option>
                <option value="class_10">Class 10 (High School)</option>
                <option value="class_11">Class 11 (Senior Secondary)</option>
                <option value="class_12">Class 12 (Senior Secondary)</option>
                <option value="undergraduate">Undergraduate Degree</option>
                <option value="competitive">Competitive Prep (JEE/NEET)</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Active Examination Targets</label>
            <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', marginTop: '4px' }}>
              {['JEE', 'NEET', 'CBSE', 'ICSE', 'Board Prep', 'Self-study'].map(target => (
                <label key={target} style={{ fontSize: '12px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={examTargets.includes(target)}
                    onChange={() => handleCheckboxChange(target)}
                    style={{ accentColor: 'var(--accent-amber)' }}
                  />
                  {target}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Learning Style Grid */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
          <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-amber)', marginBottom: 'var(--space-4)', marginTop: 0 }}>
            2. Cognitive Learning Style
          </h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 'var(--space-3)' }}>
            {[
              { id: 'visual', label: 'Visual Intuition', desc: 'Analogy-rich charts and geometrical transformations.' },
              { id: 'conceptual', label: 'Theory-First', desc: 'Structured verbal proofs and building from core axioms.' },
              { id: 'example_first', label: 'Example-driven', desc: 'Solves practical math questions before explaining theory.' },
              { id: 'equation_first', label: 'Equation derivation', desc: 'Follows absolute mathematical and symbolic derivatives first.' }
            ].map(style => (
              <div
                key={style.id}
                onClick={() => setLearningStyle(style.id)}
                style={{
                  border: learningStyle === style.id ? '1px solid var(--accent-amber)' : '1px solid var(--border-default)',
                  background: learningStyle === style.id ? 'rgba(245,158,11,0.03)' : 'var(--bg-raised)',
                  borderRadius: 'var(--r-md)',
                  padding: 'var(--space-4)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'all 0.2s'
                }}
              >
                <div style={{ fontSize: '20px', marginBottom: '8px' }}>
                  {style.id === 'visual' ? '🎨' : style.id === 'conceptual' ? '📖' : style.id === 'example_first' ? '💡' : '📐'}
                </div>
                <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  {style.label}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.3' }}>
                  {style.desc}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Confidence map sliders */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
          <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-amber)', marginBottom: 'var(--space-4)', marginTop: 0 }}>
            3. Subject Confidence Ratings
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {['Physics', 'Chemistry', 'Mathematics'].map(subj => (
              <div key={subj} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{subj}</span>
                  <span className="mono-text" style={{ color: 'var(--accent-amber)' }}>{confidence[subj]}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={confidence[subj]}
                  onChange={(e) => handleConfidenceChange(subj, e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-amber)', height: '4px', background: 'var(--bg-overlay)', borderRadius: '2px' }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Pace sliders */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
          <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-amber)', marginBottom: 'var(--space-4)', marginTop: 0 }}>
            4. Learning Speed & Depth
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '8px' }}>
              <span>Pace preference: <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{pace.replace('_', ' ')}</strong></span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
              {[
                { id: 'slow_deep', label: 'Slow & Deep', desc: 'Maximum details and checkups.' },
                { id: 'balanced', label: 'Balanced', desc: 'Steady, complete standard course.' },
                { id: 'fast_overview', label: 'Fast Overview', desc: 'Abridged summaries and fast scenes.' }
              ].map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setPace(item.id)}
                  style={{
                    padding: '8px',
                    borderRadius: 'var(--r-sm)',
                    border: 'none',
                    background: pace === item.id ? 'var(--accent-blue-dim)' : 'var(--bg-raised)',
                    color: pace === item.id ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontWeight: pace === item.id ? '600' : '400'
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* API Integration & Keys */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)' }}>
          <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-amber)', marginBottom: 'var(--space-4)', marginTop: 0 }}>
            5. API Integration & Keys
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            
            {/* Gemini API Key */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: '500' }}>
                Google Gemini API Key <span style={{ color: 'var(--accent-teal)', fontSize: '10px' }}>(Recommended - Free/Fast)</span>
              </label>
              <input
                type="password"
                value={geminiApiKey}
                onChange={(e) => setGeminiApiKey(e.target.value)}
                placeholder="AIzaSy..."
                style={{
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--r-md)',
                  padding: '10px var(--space-4)',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Obtain a Gemini key for free at the <a href="https://aistudio.google.com/" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'underline' }}>Google AI Studio Console</a>.
              </span>
            </div>

            {/* NVIDIA NIM API Key */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: '500' }}>
                NVIDIA NIM API Key <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>(Optional - Alternate LLM Provider)</span>
              </label>
              <input
                type="password"
                value={nvidiaApiKey}
                onChange={(e) => setNvidiaApiKey(e.target.value)}
                placeholder="nvapi-..."
                style={{
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--r-md)',
                  padding: '10px var(--space-4)',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Obtain a developer key from the <a href="https://build.nvidia.com/" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'underline' }}>NVIDIA Build Portal</a>.
              </span>
            </div>

          </div>
        </div>

        {/* Control actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
          <button type="submit" className="btn btn-primary" style={{ padding: '10px 24px', fontSize: '14px' }}>
            Save Profile Settings
          </button>
          
          {message && (
            <span style={{ fontSize: '12px', color: 'var(--accent-teal)', fontWeight: '500' }}>{message}</span>
          )}
        </div>

      </form>

      {/* Danger & utility Zone */}
      <hr style={{ margin: 'var(--space-8) 0' }} />

      <div style={{ maxWidth: '800px' }}>
        <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-rose)', marginBottom: 'var(--space-4)' }}>
          Database Utilities & Reset Zone
        </h3>
        
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
          <button onClick={handleExportData} className="btn btn-ghost" style={{ padding: '8px 16px', fontSize: '12px' }}>
            📥 Export profile.json
          </button>
          <button onClick={handleResetData} className="btn btn-ghost" style={{ borderColor: 'var(--accent-rose)', color: 'var(--accent-rose)', padding: '8px 16px', fontSize: '12px' }}>
            🚨 Clear database & Reset Profile
          </button>
        </div>
      </div>

    </div>
  );
}
