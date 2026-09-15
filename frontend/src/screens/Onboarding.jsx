import { useState } from 'react';
import { useProfile } from '../context/ProfileContext';
import GenerationShimmer from '../components/GenerationShimmer';

export default function Onboarding({ onComplete }) {
  const { profile, updateProfile } = useProfile();
  const [step, setStep] = useState(1);
  const [name, setName] = useState(profile.name || '');
  const [level, setLevel] = useState(profile.academic_level || 'class_11');
  const [targets, setTargets] = useState(profile.exam_target || ['JEE']);
  const [style, setStyle] = useState(profile.learning_style || 'visual');
  const [pace, setPace] = useState(profile.pace_preference || 'balanced');
  const [confMap, setConfMap] = useState(profile.confidence_map || { Chemistry: 50, Physics: 50, Mathematics: 50 });
  const [generatingSummary, setGeneratingSummary] = useState(false);

  const academicLevels = [
    { value: 'class_9', label: 'Class 9' },
    { value: 'class_10', label: 'Class 10' },
    { value: 'class_11', label: 'Class 11' },
    { value: 'class_12', label: 'Class 12' },
    { value: 'undergraduate', label: 'Undergraduate' },
    { value: 'competitive', label: 'Competitive Prep' }
  ];

  const targetOptions = ['JEE', 'NEET', 'CBSE', 'ICSE', 'Board Exams', 'Self-study'];

  const learningStyles = [
    {
      id: 'visual',
      title: 'Visual / Analogies',
      desc: 'Show me intuitive moving animations, vectors, coordinate planes, and visual shapes first.',
      icon: '🎨'
    },
    {
      id: 'conceptual',
      title: 'Conceptual grounding',
      desc: 'Focus on first principles, historical context, and the foundational "why" before math calculations.',
      icon: '🧠'
    },
    {
      id: 'example_first',
      title: 'Example-first learning',
      desc: 'Introduce a highly grounded everyday numerical example, then generalize to formula representations.',
      icon: '📝'
    },
    {
      id: 'equation_first',
      title: 'Equation-driven math',
      desc: 'Show the formal calculus or algebraic formula, isolate each factor, and derive practical meanings.',
      icon: '🧮'
    }
  ];

  const paceDetails = {
    slow_deep: {
      title: 'Slow & Deep',
      desc: 'I want multiple analogies, step-by-step conceptual checks, and detailed proofs of all theorems.'
    },
    balanced: {
      title: 'Balanced pace',
      desc: 'An even mix of visual demonstrations, structural formulas, and straightforward textbook explanations.'
    },
    fast_overview: {
      title: 'Fast Overview',
      desc: 'Give me rapid summaries, high-level connections, and key equations. Skip dense visual builds.'
    }
  };

  const handleNext = () => {
    if (step === 4) {
      setGeneratingSummary(true);
      setStep(5);
      // Simulate AI curriculum summary formulation
      setTimeout(() => {
        setGeneratingSummary(false);
      }, 1500);
    } else {
      setStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    setStep(prev => prev - 1);
  };

  const handleSubmit = async () => {
    const payload = {
      name: name || 'Learner',
      academic_level: level,
      exam_target: targets,
      learning_style: style,
      pace_preference: pace,
      confidence_map: confMap
    };
    
    await updateProfile(payload);
    onComplete();
  };

  const toggleTarget = (t) => {
    setTargets(prev =>
      prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]
    );
  };

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        background: 'var(--bg-base)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '2rem'
      }}
    >
      {/* Container Smart Onboarding Card */}
      <div
        className="learnos-card"
        style={{
          width: '100%',
          maxWidth: '680px',
          minHeight: '460px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: 'var(--space-6)',
          border: '1px solid var(--border-default)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.1)'
        }}
      >
        {/* Progress Indicator Head */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            LearnOS Intake Form
          </span>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            {[1, 2, 3, 4, 5].map(idx => (
              <div
                key={idx}
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: idx === step ? 'var(--accent-amber)' : idx < step ? 'var(--accent-teal)' : 'var(--bg-overlay)',
                  border: idx === step ? 'none' : '1px solid var(--border-default)',
                  transition: 'all 0.3s'
                }}
              />
            ))}
          </div>
        </div>

        {/* Dynamic Step Content Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', fontWeight: '400' }}>
                Tell me about yourself.
              </h2>
              <div className="form-group">
                <label className="form-label">What is your name?</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Abhishek"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  style={{ fontSize: '15px' }}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Academic level</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)' }}>
                  {academicLevels.map(al => (
                    <button
                      key={al.value}
                      onClick={() => setLevel(al.value)}
                      style={{
                        padding: '10px',
                        borderRadius: 'var(--r-sm)',
                        background: level === al.value ? 'var(--accent-blue-dim)' : 'var(--bg-raised)',
                        color: level === al.value ? 'var(--accent-blue)' : 'var(--text-secondary)',
                        border: level === al.value ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        fontSize: '13px',
                        fontWeight: level === al.value ? 600 : 400,
                        transition: 'all 0.2s'
                      }}
                    >
                      {al.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Exam targets</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                  {targetOptions.map(t => {
                    const isSel = targets.includes(t);
                    return (
                      <button
                        key={t}
                        onClick={() => toggleTarget(t)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '100px',
                          background: isSel ? 'var(--accent-amber-dim)' : 'var(--bg-raised)',
                          color: isSel ? 'var(--accent-amber)' : 'var(--text-secondary)',
                          border: isSel ? '1px solid var(--accent-amber)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          fontSize: '12px',
                          fontWeight: isSel ? 600 : 400,
                          transition: 'all 0.2s'
                        }}
                      >
                        {t}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', fontWeight: '400' }}>
                How do you process information best?
              </h2>
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                Your learning style dictates how the explanation engine conditions narration and Manim shapes.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)' }}>
                {learningStyles.map(ls => (
                  <div
                    key={ls.id}
                    onClick={() => setStyle(ls.id)}
                    className="learnos-card interactive"
                    style={{
                      padding: 'var(--space-4)',
                      background: style === ls.id ? 'var(--bg-raised)' : 'var(--bg-surface)',
                      borderColor: style === ls.id ? 'var(--accent-amber)' : 'var(--border-subtle)',
                      borderWidth: '1px',
                      display: 'flex',
                      gap: 'var(--space-3)',
                      alignItems: 'flex-start'
                    }}
                  >
                    <span style={{ fontSize: '24px' }}>{ls.icon}</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <h4 style={{ fontSize: '14px', color: style === ls.id ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                        {ls.title}
                      </h4>
                      <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>{ls.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', fontWeight: '400' }}>
                Subject confidence map
              </h2>
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                Your initial self-assessment ranks where we suggest starting curriculums first.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginTop: 'var(--space-2)' }}>
                {Object.keys(confMap).map(subj => (
                  <div key={subj} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                      <span style={{ fontWeight: '500' }}>{subj}</span>
                      <span className="mono-text" style={{ color: 'var(--accent-blue)' }}>{confMap[subj]}%</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={confMap[subj]}
                        onChange={e => setConfMap(prev => ({ ...prev, [subj]: parseInt(e.target.value) }))}
                        style={{
                          flex: 1,
                          height: '6px',
                          background: 'var(--bg-overlay)',
                          borderRadius: '3px',
                          outline: 'none',
                          cursor: 'pointer',
                          accentColor: 'var(--accent-blue)'
                        }}
                      />
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)', minWidth: '70px', textAlign: 'right' }}>
                        {confMap[subj] < 40 ? 'Reviewing base' : confMap[subj] < 75 ? 'Getting there' : 'Very confident'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', fontWeight: '400' }}>
                Select learning pace
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
                {Object.keys(paceDetails).map(pKey => (
                  <div
                    key={pKey}
                    onClick={() => setPace(pKey)}
                    className="learnos-card interactive"
                    style={{
                      background: pace === pKey ? 'var(--bg-raised)' : 'var(--bg-surface)',
                      borderColor: pace === pKey ? 'var(--accent-blue)' : 'var(--border-subtle)',
                      borderWidth: '1px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px'
                    }}
                  >
                    <h4 style={{ fontSize: '14px', color: pace === pKey ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                      {paceDetails[pKey].title}
                    </h4>
                    <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      {paceDetails[pKey].desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', fontWeight: '400' }}>
                AI Curriculum Summary
              </h2>
              
              {generatingSummary ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', padding: 'var(--space-4)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    Configuring personalized explanation agents...
                  </span>
                  <GenerationShimmer rows={3} />
                </div>
              ) : (
                <div
                  className="learnos-card"
                  style={{
                    background: 'var(--bg-raised)',
                    borderColor: 'var(--border-strong)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-3)'
                  }}
                >
                  <h4 style={{ fontSize: '16px', color: 'var(--accent-amber)' }}>
                    Welcome to LearnOS, {name}!
                  </h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                    Based on your profile, I have tailored the learning settings:
                  </p>
                  <ul
                    style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      paddingLeft: 'var(--space-4)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                      listStyleType: 'square'
                    }}
                  >
                    <li>
                      I will render <strong>Visual Analogies</strong> using coordinate vectors and scale animations.
                    </li>
                    <li>
                      Your syllabus targets <strong>{targets.join(', ')}</strong> with initial focus on improving Chemistry ({confMap.Chemistry}% confidence).
                    </li>
                    <li>
                      Narration flow set to a <strong>{paceDetails[pace]?.title}</strong> profile.
                    </li>
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Navigation Button Row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-4)' }}>
          {step > 1 && step < 5 ? (
            <button onClick={handleBack} className="btn btn-ghost" style={{ fontSize: '13px' }}>
              ← Back
            </button>
          ) : (
            <div />
          )}

          {step < 5 ? (
            <button onClick={handleNext} className="btn btn-primary" style={{ minWidth: '100px' }}>
              Next Step
            </button>
          ) : (
            !generatingSummary && (
              <button onClick={handleSubmit} className="btn btn-primary" style={{ minWidth: '140px', background: 'var(--accent-teal)', color: 'var(--text-inverted)' }}>
                Start Learning →
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
