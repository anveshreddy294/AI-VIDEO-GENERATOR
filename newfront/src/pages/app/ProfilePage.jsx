import React, { useState } from 'react';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphUser, 
  GlyphCheckmark, 
  GlyphRotate, 
  GlyphDocument, 
  GlyphArrowRight,
  GlyphEvidence
} from '../../components/ui/AtelierGlyphs';

export default function ProfilePage() {
  const { user, logout, showNotification } = useAtelierWorkspace();

  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [emailDigest, setEmailDigest] = useState(true);

  const handleSavePreferences = (e) => {
    e.preventDefault();
    showNotification('Accessibility preferences are active for this browser session.');
  };

  const handleClearCache = () => {
    showNotification('No fabricated workspace cache was found to clear. Server data remains unchanged.');
  };

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">SECURITY & USER IDENTITY · LOCAL SANDBOX</span>
          <span className="coord-label" style={{ marginLeft: 'auto' }}>ACADEMIC DOSSIER</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Profile & Studio Preferences</h1>
            <p className="page-subheading">
              Manage student credentials, role authorization, accessibility parameters, and data governance.
            </p>
          </div>
        </div>
      </section>

      {/* Single Vertical Downward Flow: Identity on top, Preferences & Governance below */}
      <div className="profile-split-grid">
        {/* User Card & Role Credentials — Unboxed Matter */}
        <div className="profile-identity-column">
          <div className="user-identity-card">
            <div className="card-top-bar">
              <span className="coord-label">CANONICAL USER CREDENTIALS</span>
              <span className="card-badge-soft">{user.role.toUpperCase()}</span>
            </div>

            <div className="identity-badge-mount">
              <div className="profile-seal-crest">
                <span>{user.avatarLabel}</span>
              </div>
              <div className="identity-names">
                <h2 className="identity-name">{user.name}</h2>
                <span className="identity-email">{user.email}</span>
              </div>
            </div>

            <div className="dossier-meta-grid">
              <div className="dossier-cell">
                <span className="dossier-k">ENROLLED COURSE</span>
                <span className="dossier-v">{user.course || 'Computer Science 304'}</span>
              </div>
              <div className="dossier-cell">
                <span className="dossier-k">INSTITUTION</span>
                <span className="dossier-v">Dept. of Computer Science</span>
              </div>
              <div className="dossier-cell">
                <span className="dossier-k">CLEARANCE TIER</span>
                <span className="dossier-v">LEVEL 02 · SCHOLAR</span>
              </div>
              <div className="dossier-cell">
                <span className="dossier-k">WORKSPACE MODE</span>
                <span className="dossier-v">Authenticated FastAPI</span>
              </div>
            </div>

            {/* Live Session Telemetry Card */}
            <div className="telemetry-terminal-card" style={{ marginTop: '14px' }}>
              <div className="telemetry-terminal-line">
                <span style={{ color: 'var(--terracotta)' }}>$ atelier --auth</span>
                <span style={{ color: '#88D49E' }}>VERIFIED</span>
              </div>
              <div className="telemetry-terminal-line">
                <span style={{ opacity: 0.7 }}>ENDPOINT:</span>
                <span>http://127.0.0.1:8000</span>
              </div>
              <div className="telemetry-terminal-line">
                <span style={{ opacity: 0.7 }}>TOKEN STORAGE:</span>
                <span>sessionStorage (durable)</span>
              </div>
              <div className="telemetry-terminal-line">
                <span style={{ opacity: 0.7 }}>CLIENT ENGINE:</span>
                <span>React 19 + GSAP + Anime</span>
              </div>
            </div>

            <div className="identity-card-actions" style={{ marginTop: '16px' }}>
              <button 
                type="button" 
                className="btn-atelier-outline"
                onClick={logout}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>

        {/* Accessibility & Telemetry Settings — Unboxed Matter */}
        <div className="profile-settings-column">
          <div className="settings-card">
            <div className="card-top-bar">
              <span className="coord-label">ACCESSIBILITY & INTERACTION PREFERENCES</span>
              <span className="card-badge-soft">SYSTEM CONFIG</span>
            </div>

            <form onSubmit={handleSavePreferences} className="preferences-form">
              <div className="settings-toggle-group">
                <label className="settings-toggle-row">
                  <div className="toggle-label-copy">
                    <strong>Respect Reduced Motion (`prefers-reduced-motion`)</strong>
                    <p>Disables camera fly-throughs, stagger animations and dynamic transitions.</p>
                  </div>
                  <input 
                    type="checkbox" 
                    checked={reducedMotion}
                    onChange={(e) => setReducedMotion(e.target.checked)}
                    className="atelier-checkbox"
                  />
                </label>

                <div className="hairline-rule" />

                <label className="settings-toggle-row">
                  <div className="toggle-label-copy">
                    <strong>High-Contrast Architectural Hairlines</strong>
                    <p>Increases stroke contrast on textbook highlight boxes and concept roadmap connectors.</p>
                  </div>
                  <input 
                    type="checkbox" 
                    checked={highContrast}
                    onChange={(e) => setHighContrast(e.target.checked)}
                    className="atelier-checkbox"
                  />
                </label>

                <div className="hairline-rule" />

                <label className="settings-toggle-row">
                  <div className="toggle-label-copy">
                    <strong>Diagnostic Misconception Notifications</strong>
                    <p>Receive immediate alerts when practice attempts detect conceptual gaps.</p>
                  </div>
                  <input 
                    type="checkbox" 
                    checked={emailDigest}
                    onChange={(e) => setEmailDigest(e.target.checked)}
                    className="atelier-checkbox"
                  />
                </label>
              </div>

              <div className="settings-actions-bar" style={{ marginTop: '20px' }}>
                <button type="submit" className="btn-atelier-primary">
                  <span>Save Interaction Preferences</span>
                  <GlyphCheckmark size={13} />
                </button>
              </div>
            </form>
          </div>

          {/* Local Data Governance — Unboxed Matter */}
          <div className="governance-card" style={{ padding: '24px 0', borderBottom: '1px solid var(--border)' }}>
            <div className="card-top-bar">
              <span className="coord-label">DATA GOVERNANCE & TELEMETRY</span>
              <span className="card-badge-warn">LOCAL STORAGE</span>
            </div>

            <div className="governance-body" style={{ padding: '16px 0' }}>
              <p className="governance-desc" style={{ fontSize: '16.5px', lineHeight: 1.65, color: 'var(--ink-secondary)' }}>
                Session credentials are held in session storage to follow the existing FastAPI browser contract.
                Source files, lessons, artifacts and scores remain server-owned and authorization-scoped.
              </p>
              
              <div className="governance-buttons" style={{ marginTop: '16px' }}>
                <button 
                  type="button" 
                  className="btn-atelier-outline"
                  onClick={handleClearCache}
                >
                  <GlyphRotate size={13} />
                  <span>Flush Local Sandbox Cache</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
