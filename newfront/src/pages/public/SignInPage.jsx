import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { toUserMessage } from '../../services/api/errors';
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
  const { login, signup, authStatus } = useAtelierWorkspace();
  const navigate = useNavigate();

  // Mode: 'signin' | 'signup'
  const [authMode, setAuthMode] = useState('signin');

  // Sign In fields
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');

  // Sign Up fields
  const [signUpName, setSignUpName] = useState('');
  const [signUpEmail, setSignUpEmail] = useState('');
  const [signUpPassword, setSignUpPassword] = useState('');
  const [agreeHonorCode, setAgreeHonorCode] = useState(true);
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSignIn = async (e) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      const identity = await login(signInEmail, signInPassword);
      navigate(['instructor', 'admin'].includes(identity?.profile?.role) ? '/educator' : '/app/dashboard');
    } catch (error) {
      setFormError(toUserMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    if (!agreeHonorCode) {
      setFormError('Please agree to the truthful citation and academic integrity principles.');
      return;
    }
    setFormError(null);
    setIsSubmitting(true);
    try {
      const result = await signup(signUpEmail, signUpPassword, signUpName);
      if (result?.confirmationRequired) {
        setAuthMode('signin');
        setSignInEmail(signUpEmail);
        setFormError('Account created. Confirm the email address, then sign in.');
      } else {
        navigate(['instructor', 'admin'].includes(result?.profile?.role) ? '/educator' : '/app/dashboard');
      }
    } catch (error) {
      setFormError(toUserMessage(error));
    } finally {
      setIsSubmitting(false);
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
              src="/assets/student_studying.jpg" 
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

                {formError && <div className="signin-disclaimer-box" role="alert"><p>{formError}</p></div>}
                <button type="submit" disabled={isSubmitting || authStatus === 'loading'} className="btn-atelier-primary signin-submit-btn">
                  <span>{isSubmitting ? 'Authenticating…' : 'Enter Workspace'}</span>
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

                <div className="signin-disclaimer-box">
                  <span className="coord-label">ROLE AUTHORITY</span>
                  <p>Your account role is assigned by the backend profile. This form cannot grant educator access.</p>
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

                {formError && <div className="signin-disclaimer-box" role="alert"><p>{formError}</p></div>}
                <button type="submit" disabled={isSubmitting || authStatus === 'loading'} className="btn-atelier-primary signin-submit-btn">
                  <span>{isSubmitting ? 'Creating…' : 'Initialize Scholar Account'}</span>
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
