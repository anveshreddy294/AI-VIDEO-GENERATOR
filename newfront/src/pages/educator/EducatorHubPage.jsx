import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphDag, 
  GlyphCrosshair, 
  GlyphArrowRight, 
  GlyphCheckmark, 
  GlyphUser, 
  GlyphDocument 
} from '../../components/ui/AtelierGlyphs';

export default function EducatorHubPage() {
  const { user, toggleRole, educatorAnalytics, showNotification } = useAtelierWorkspace();
  const navigate = useNavigate();

  const handleDispatchIntervention = (conceptTitle) => {
    showNotification(`Targeted remediation sequence dispatched for "${conceptTitle}" to flagged cohort students.`);
  };

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">INSTRUCTOR GOVERNANCE PORTAL · COHORT TELEMETRY</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Educator Analytics & Intervention Console</h1>
            <p className="page-subheading">
              Curriculum telemetry across <strong>{educatorAnalytics.courseName}</strong> ({educatorAnalytics.enrolledStudents} Enrolled Scholars)
            </p>
          </div>
          <div className="header-role-controls">
            <button 
              type="button" 
              className="btn-atelier-outline"
              onClick={toggleRole}
            >
              <span>Current Role: {user.role.toUpperCase()} (Switch)</span>
            </button>
          </div>
        </div>
      </section>

      {/* Overview Stat Strip */}
      <div className="educator-stat-strip">
        <div className="stat-card">
          <span className="coord-label">ENROLLED SCHOLARS</span>
          <strong className="stat-value">{educatorAnalytics.enrolledStudents}</strong>
          <span className="stat-sub">Active in Chapter 3</span>
        </div>

        <div className="stat-card">
          <span className="coord-label">AVERAGE COHORT MASTERY</span>
          <strong className="stat-value">{educatorAnalytics.averageMastery}</strong>
          <span className="stat-sub">Across 8 Relational Invariants</span>
        </div>

        <div className="stat-card">
          <span className="coord-label">ACTIVE INTERVENTIONS</span>
          <strong className="stat-value">{educatorAnalytics.misconceptionAlerts.length}</strong>
          <span className="stat-sub">Targeted Misconception Alerts</span>
        </div>
      </div>

      {/* Main 2-Column Intervention Grid */}
      <div className="educator-grid-layout">
        {/* Left Column: Flagged Misconceptions Queue */}
        <div className="educator-column">
          <div className="atelier-card alert-panel-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphCrosshair size={14} />
                <span className="coord-label">FLAGGED CONCEPTUAL MISCONCEPTIONS</span>
              </div>
              <span className="card-badge-warn">ACTION REQUIRED</span>
            </div>

            <div className="alerts-list">
              {educatorAnalytics.misconceptionAlerts.map(alert => (
                <div key={alert.conceptId} className="alert-item-card">
                  <div className="alert-item-header">
                    <span className="coord-label">CONCEPT: {alert.conceptId.toUpperCase()}</span>
                    <span className="alert-flag-pill">{alert.flaggedCount} STUDENTS FLAGGED</span>
                  </div>

                  <h3 className="alert-title">{alert.conceptTitle}</h3>
                  <p className="alert-explanation">{alert.explanation}</p>

                  <div className="alert-actions-bar">
                    <button 
                      type="button" 
                      className="btn-atelier-terracotta"
                      onClick={() => handleDispatchIntervention(alert.conceptTitle)}
                    >
                      <span>Dispatch Remediation Micro-Lesson</span>
                      <GlyphArrowRight size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Curriculum Graph Health */}
        <div className="educator-column">
          <div className="atelier-card graph-health-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphDag size={14} />
                <span className="coord-label">CURRICULUM TOPOLOGY HEALTH</span>
              </div>
              <span className="card-badge-soft">DIAGNOSTIC MATRIX</span>
            </div>

            <div className="curriculum-matrix-list">
              <div className="matrix-row">
                <div className="matrix-info">
                  <strong>Tuple Calculus & Relation Definition</strong>
                  <span className="coord-label">PAGE 4 · ROOT NODE</span>
                </div>
                <span className="matrix-score-good">94% Retention</span>
              </div>

              <div className="matrix-row">
                <div className="matrix-info">
                  <strong>Entity Integrity & Primary Key Invariants</strong>
                  <span className="coord-label">PAGE 7 · 0 PREREQUISITES</span>
                </div>
                <span className="matrix-score-good">88% Retention</span>
              </div>

              <div className="matrix-row">
                <div className="matrix-info">
                  <strong>Referential Integrity & Nullable Foreign Keys</strong>
                  <span className="coord-label">PAGE 9 · 1 PREREQUISITE</span>
                </div>
                <span className="matrix-score-warn">62% Retention (Intervention)</span>
              </div>

              <div className="matrix-row">
                <div className="matrix-info">
                  <strong>First Normal Form (1NF) Atomicity</strong>
                  <span className="coord-label">PAGE 14 · NORMALIZATION</span>
                </div>
                <span className="matrix-score-warn">71% Retention</span>
              </div>
            </div>

            <div className="matrix-footer-action">
              <button 
                type="button" 
                className="btn-atelier-primary"
                onClick={() => navigate('/app/studio')}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <span>Preview Student Studio Lesson</span>
                <GlyphArrowRight size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
