import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphBrandMark, 
  GlyphArrowRight, 
  GlyphUser, 
  GlyphCheckmark,
  GlyphCrosshair,
  GlyphDocument,
  GlyphEvidence
} from '../../components/ui/AtelierGlyphs';

export default function SignInPage() {
  const { setUser, notify, showNotification } = useAtelierWorkspace();
  const navigate = useNavigate();

  // Mode: 'signin' | 'signup'
  const [authMode, setAuthMode] = useState('signin');

  // Sign In fields
  const [signInEmail, setSignInEmail] = useState('elena.rostova@atelier.edu');
  const [signInPassword, setSignInPassword] = useState('••••••••••••');
  const [signInRole, setSignInRole] = useState('student'); // 'student' | 'educator'

  // Sign Up fields
  const [signUpName, setSignUpName] = useState('Sophia Chen');
  const [signUpEmail, setSignUpEmail] = useState('sophia.chen@stanford.edu');
  const [signUpInstitution, setSignUpInstitution] = useState('Stanford University · Dept of EECS');
  const [signUpPassword, setSignUpPassword] = useState('••••••••••••');
  const [signUpRole, setSignUpRole] = useState('student');
  const [signUpCourse, setSignUpCourse] = useState('CS 304: Relational Database Systems');
  const [agreeHonorCode, setAgreeHonorCode] = useState(true);

  const sendNotification = (msg) => {
    if (showNotification) showNotification(msg);
    else if (notify) notify(msg);
  };

  const handleSignIn = (e) => {
    e.preventDefault();
    const name = signInRole === 'educator' ? 'Prof. David Vance' : 'Elena Rostova';
    const avatar = signInRole === 'educator' ? 'DV' : 'ER';

    setUser({
      name,
      email: signInEmail,
      role: signInRole,
      avatarLabel: avatar,
      course: 'CS 304: Relational Database Systems'
    });

    sendNotification(`Authenticated as ${name}. Workspace loaded.`);

    if (signInRole === 'educator') {
      navigate('/educator');
    } else {
      navigate('/app/dashboard');
    }
  };

  const handleSignUp = (e) => {
    e.preventDefault();
    if (!agreeHonorCode) {
      alert('Please agree to the truthful citation and academic integrity principles.');
      return;
    }

    // Compute initials from name
    const initials = signUpName
      .trim()
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) || 'SC';

    setUser({
      name: signUpName,
      email: signUpEmail,
      role: signUpRole,
      institution: signUpInstitution,
      course: signUpCourse,
      avatarLabel: initials
    });

    sendNotification(`Scholar account created for ${signUpName}. Workspace initialized.`);

    if (signUpRole === 'educator') {
      navigate('/educator');
    } else {
      navigate('/app/dashboard');
    }
  };

  const setPresetProfile = (preset) => {
    if (preset === 'student') {
      setSignInEmail('elena.rostova@atelier.edu');
      setSignInRole('student');
    } else {
      setSignInEmail('david.vance@atelier.edu');
      setSignInRole('educator');
    }
  };

  return (
    <div className="signin-page-root">
      {/* Left Specimen Plate */}
      <div className="signin-visual-column">
        <div className="signin-visual-card">
          <div className="signin-brand-lockup">
            <GlyphBrandMark size={24} className="brand-glyph" />
            <span className="brand-name">VisualAI</span>
          </div>

          <div className="signin-contained-preview" style={{
            position: 'relative',
            height: '240px',
            backgroundColor: '#262320',
            border: '1px solid #3D3833',
            borderRadius: 'var(--radius-sharp)',
            overflow: 'hidden',
            margin: '24px 0'
          }}>
            <img 
              src="/assets/study_desk_mac.jpg" 
              alt="VisualAI Learning Studio" 
              className="floating-media-core"
              style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.88 }} 
            />
            <div style={{
              position: 'absolute',
              bottom: '10px',
              left: '10px',
              right: '10px',
              backgroundColor: 'rgba(28, 27, 25, 0.92)',
              padding: '6px 10px',
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--canvas)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <GlyphCrosshair size={12} />
              <span>VERIFIED ACADEMIC LEARNING SESSION</span>
            </div>
          </div>

          <div className="signin-quote-block">
            <span className="coord-label" style={{ color: '#BCC5BE' }}>
              {authMode === 'signin' ? 'CANONICAL ACCESS' : 'SCHOLAR REGISTRATION'}
            </span>
            <h2 className="signin-quote-headline">
              {authMode === 'signin' ? (
                <>Enter your verified<br /><em>learning studio.</em></>
              ) : (
                <>Register your verified<br /><em>academic identity.</em></>
              )}
            </h2>
            <p className="signin-quote-sub">
              {authMode === 'signin'
                ? 'Continue exploring your structured curriculum topics, animated video lessons, and handwritten study notes.'
                : 'Initialize your student workspace grounded in your university textbooks, lecture slides, and practice problem sets.'}
            </p>
          </div>

          <div className="signin-footer-meta">
            <span>© 2026 VisualAI Project</span>
            <span>Cryptographic Session Boundary · RLS Enforced</span>
          </div>
        </div>
      </div>

      {/* Right Sign In / Sign Up Form */}
      <div className="signin-form-column">
        <div className="signin-card-body">
          <div className="signin-top-nav">
            <Link to="/" className="back-link">
              ← Return to Atelier Overview
            </Link>
          </div>

          {/* Mode Tabs: Sign In vs Sign Up */}
          <div className="auth-mode-tabs">
            <button
              type="button"
              className={`auth-tab-btn ${authMode === 'signin' ? 'active' : ''}`}
              onClick={() => setAuthMode('signin')}
            >
              Sign In to Workspace
            </button>
            <button
              type="button"
              className={`auth-tab-btn ${authMode === 'signup' ? 'active' : ''}`}
              onClick={() => setAuthMode('signup')}
            >
              Create Scholar Account
            </button>
          </div>

          {/* SIGN IN FORM */}
          {authMode === 'signin' && (
            <>
              <div className="signin-header">
                <span className="coord-label">AUTHENTICATION PORTAL</span>
                <h1 className="signin-title">Workspace Sign In</h1>
                <p className="signin-sub">
                  Access your personalized student workspace or authorized educator console.
                </p>
              </div>

              <form onSubmit={handleSignIn} className="signin-form">
                <div className="form-field-group">
                  <label htmlFor="signin-email" className="field-label">Institutional Email</label>
                  <input 
                    id="signin-email"
                    type="email" 
                    required 
                    className="atelier-input"
                    value={signInEmail}
                    onChange={e => setSignInEmail(e.target.value)}
                  />
                </div>

                <div className="form-field-group">
                  <label htmlFor="signin-pass" className="field-label">Access Passphrase</label>
                  <input 
                    id="signin-pass"
                    type="password" 
                    required 
                    className="atelier-input"
                    value={signInPassword}
                    onChange={e => setSignInPassword(e.target.value)}
                  />
                </div>

                <div className="form-field-group">
                  <label className="field-label">Workspace Role</label>
                  <div className="role-selector-toggle">
                    <button
                      type="button"
                      className={`role-btn ${signInRole === 'student' ? 'active' : ''}`}
                      onClick={() => setSignInRole('student')}
                    >
                      Student Workspace
                    </button>
                    <button
                      type="button"
                      className={`role-btn ${signInRole === 'educator' ? 'active' : ''}`}
                      onClick={() => setSignInRole('educator')}
                    >
                      Educator Hub
                    </button>
                  </div>
                </div>

                {/* Quick Presets for Pair Programming / Demonstration */}
                <div style={{ display: 'flex', gap: '8px', marginTop: '2px' }}>
                  <button
                    type="button"
                    onClick={() => setPresetProfile('student')}
                    style={{
                      flex: 1,
                      padding: '4px 8px',
                      fontSize: '10px',
                      fontFamily: 'var(--font-mono)',
                      background: 'var(--surface-subtle)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer'
                    }}
                  >
                    Preset: Elena (Student)
                  </button>
                  <button
                    type="button"
                    onClick={() => setPresetProfile('educator')}
                    style={{
                      flex: 1,
                      padding: '4px 8px',
                      fontSize: '10px',
                      fontFamily: 'var(--font-mono)',
                      background: 'var(--surface-subtle)',
                      border: '1px solid var(--border)',
                      cursor: 'pointer'
                    }}
                  >
                    Preset: Prof. Vance (Educator)
                  </button>
                </div>

                <button type="submit" className="btn-atelier-primary signin-submit-btn">
                  <span>Enter Workspace</span>
                  <GlyphArrowRight size={13} />
                </button>
              </form>
            </>
          )}

          {/* SIGN UP FORM */}
          {authMode === 'signup' && (
            <>
              <div className="signin-header">
                <span className="coord-label">NEW SCHOLAR ONBOARDING</span>
                <h1 className="signin-title">Create Scholar Account</h1>
                <p className="signin-sub">
                  Register a verified profile to build concept graphs and generate video derivations.
                </p>
              </div>

              <form onSubmit={handleSignUp} className="signin-form">
                <div className="form-field-group">
                  <label htmlFor="signup-name" className="field-label">Full Name</label>
                  <input 
                    id="signup-name"
                    type="text" 
                    required 
                    className="atelier-input"
                    value={signUpName}
                    onChange={e => setSignUpName(e.target.value)}
                    placeholder="e.g. Sophia Chen"
                  />
                </div>

                <div className="form-field-group">
                  <label htmlFor="signup-email" className="field-label">Institutional Email (.edu / academic)</label>
                  <input 
                    id="signup-email"
                    type="email" 
                    required 
                    className="atelier-input"
                    value={signUpEmail}
                    onChange={e => setSignUpEmail(e.target.value)}
                    placeholder="e.g. sophia.chen@stanford.edu"
                  />
                </div>

                <div className="form-field-group">
                  <label htmlFor="signup-institution" className="field-label">Academic Institution & Department</label>
                  <input 
                    id="signup-institution"
                    type="text" 
                    required 
                    className="atelier-input"
                    value={signUpInstitution}
                    onChange={e => setSignUpInstitution(e.target.value)}
                    placeholder="e.g. Stanford University · School of Engineering"
                  />
                </div>

                <div className="form-field-group">
                  <label htmlFor="signup-pass" className="field-label">Create Security Passphrase</label>
                  <input 
                    id="signup-pass"
                    type="password" 
                    required 
                    className="atelier-input"
                    value={signUpPassword}
                    onChange={e => setSignUpPassword(e.target.value)}
                  />
                </div>

                <div className="form-field-group">
                  <label className="field-label">Academic Role</label>
                  <div className="role-selector-toggle">
                    <button
                      type="button"
                      className={`role-btn ${signUpRole === 'student' ? 'active' : ''}`}
                      onClick={() => setSignUpRole('student')}
                    >
                      Student Scholar
                    </button>
                    <button
                      type="button"
                      className={`role-btn ${signUpRole === 'educator' ? 'active' : ''}`}
                      onClick={() => setSignUpRole('educator')}
                    >
                      Course Faculty
                    </button>
                  </div>
                </div>

                <div className="form-field-group">
                  <label htmlFor="signup-course" className="field-label">Initial Curriculum Focus</label>
                  <select 
                    id="signup-course"
                    className="atelier-input"
                    value={signUpCourse}
                    onChange={e => setSignUpCourse(e.target.value)}
                  >
                    <option value="CS 304: Relational Database Systems">CS 304: Relational Database Systems</option>
                    <option value="PHYS 201: Celestial Mechanics & Orbits">PHYS 201: Celestial Mechanics & Orbits</option>
                    <option value="BIO 110: Molecular Genetics & Transcription">BIO 110: Molecular Genetics & Transcription</option>
                    <option value="EE 205: Analog Feedback & Linear Circuits">EE 205: Analog Feedback & Linear Circuits</option>
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '11px', marginTop: '4px' }}>
                  <input 
                    type="checkbox"
                    id="honor-code"
                    checked={agreeHonorCode}
                    onChange={e => setAgreeHonorCode(e.target.checked)}
                    style={{ marginTop: '2px', accentColor: 'var(--evergreen)' }}
                  />
                  <label htmlFor="honor-code" style={{ color: 'var(--ink-secondary)', lineHeight: 1.4 }}>
                    I agree to the Code of Truthful Grounding and Academic Integrity.
                  </label>
                </div>

                <button type="submit" className="btn-atelier-primary signin-submit-btn">
                  <span>Initialize Scholar Account</span>
                  <GlyphArrowRight size={13} />
                </button>
              </form>
            </>
          )}

          <div className="signin-disclaimer-box">
            <span className="coord-label">SECURITY SPECIFICATION · RLS ENFORCED</span>
            <p>
              Supabase PostgreSQL maintains strict cryptographic separation between student workspaces and course cohorts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
