import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphUser, 
  GlyphCheckmark, 
  GlyphRotate, 
  GlyphDocument, 
  GlyphArrowRight 
} from '../../components/ui/AtelierGlyphs';

export default function ProfilePage() {
  const { user, toggleRole, showNotification } = useAtelierWorkspace();
  const navigate = useNavigate();

  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [emailDigest, setEmailDigest] = useState(true);

  const handleSavePreferences = (e) => {
    e.preventDefault();
    showNotification('Workspace preferences updated successfully.');
  };

  const handleClearCache = () => {
    showNotification('Local telemetry cache flushed. Sandbox reset.');
  };

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">SECURITY & USER IDENTITY · LOCAL SANDBOX</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Profile & Studio Preferences</h1>
            <p className="page-subheading">
              Manage student credentials, role authorization, accessibility parameters, and data governance.
            </p>
          </div>
          <button 
            type="button" 
            className="btn-atelier-outline"
            onClick={toggleRole}
          >
            <span>Switch Role ({user.role === 'student' ? 'To Instructor' : 'To Student'})</span>
          </button>
        </div>
      </section>

      {/* 2-Column Split: Identity & Role on Left, Preferences & Governance on Right */}
      <div className="profile-split-grid">
        {/* Left Column: User Card & Role Credentials */}
        <div className="profile-identity-column">
          <div className="atelier-card user-identity-card">
            <div className="card-top-bar">
              <span className="coord-label">CANONICAL USER CREDENTIALS</span>
              <span className="card-badge-soft">{user.role.toUpperCase()}</span>
            </div>

            <div className="identity-badge-mount">
              <div className="identity-avatar-monogram">
                {user.avatarLabel}
              </div>
              <div className="identity-names">
                <h2 className="identity-name">{user.name}</h2>
                <span className="identity-email">{user.email}</span>
              </div>
            </div>

            <div className="identity-details-list">
              <div className="identity-detail-row">
                <span className="coord-label">ENROLLED COURSE:</span>
                <strong>{user.course}</strong>
              </div>
              <div className="identity-detail-row">
                <span className="coord-label">INSTITUTION:</span>
                <span>Department of Computer Science</span>
              </div>
              <div className="identity-detail-row">
                <span className="coord-label">WORKSPACE MODE:</span>
                <span>Self-Hosted Local Sandbox</span>
              </div>
            </div>

            <div className="identity-card-actions">
              <button 
                type="button" 
                className="btn-atelier-outline"
                onClick={() => navigate('/signin')}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <span>Sign Out of Sandbox</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Accessibility & Telemetry Settings */}
        <div className="profile-settings-column">
          <div className="atelier-card settings-card">
            <div className="card-top-bar">
              <span className="coord-label">ACCESSIBILITY & INTERACTION PREFERENCES</span>
              <span className="card-badge-soft">SYSTEM CONFIG</span>
            </div>

            <form onSubmit={handleSavePreferences} className="preferences-form">
              <div className="settings-toggle-group">
                <label className="settings-toggle-row">
                  <div className="toggle-label-copy">
                    <strong>Respect Reduced Motion (`prefers-reduced-motion`)</strong>
                    <p>Disables vector player camera fly-throughs and transitions.</p>
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

              <div className="settings-actions-bar">
                <button type="submit" className="btn-atelier-primary">
                  <span>Save Interaction Preferences</span>
                  <GlyphCheckmark size={12} />
                </button>
              </div>
            </form>
          </div>

          {/* Local Data Governance */}
          <div className="atelier-card governance-card">
            <div className="card-top-bar">
              <span className="coord-label">DATA GOVERNANCE & TELEMETRY</span>
              <span className="card-badge-warn">LOCAL STORAGE</span>
            </div>

            <div className="governance-body">
              <p className="governance-desc">
                All uploaded textbooks and practice scores reside in your local browser sandbox and
                FastAPI memory. No third-party behavioral trackers or cookies are loaded.
              </p>
              
              <div className="governance-buttons">
                <button 
                  type="button" 
                  className="btn-atelier-outline"
                  onClick={handleClearCache}
                >
                  <GlyphRotate size={12} />
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
