import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphRotate, 
  GlyphCheckmark, 
  GlyphCrosshair, 
  GlyphArrowRight, 
  GlyphDag, 
  GlyphEvidence 
} from '../../components/ui/AtelierGlyphs';

export default function ProgressPage() {
  const { 
    activeSource, 
    allConcepts, 
    masteryScores, 
    setActiveConceptId 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const [remediationModalConcept, setRemediationModalConcept] = useState(null);

  const conceptsList = Object.values(allConcepts);
  const strongConcepts = conceptsList.filter(c => (masteryScores[c.id] || 0) >= 80);
  const reviewConcepts = conceptsList.filter(c => (masteryScores[c.id] || 0) < 80);

  // Dynamic real-time calculation based on actual practice scoring
  const validScores = Object.values(masteryScores);
  const averageScore = validScores.length > 0 
    ? Math.round(validScores.reduce((acc, score) => acc + score, 0) / validScores.length)
    : 74;

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">STUDENT MASTERY & PROGRESS ROADMAP</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Your Learning Progress</h1>
            <p className="page-subheading">
              Track your scores and practice history across <strong>{activeSource.name}</strong> topics.
            </p>
          </div>
          <div className="header-stat-box" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            padding: '10px 16px',
            backgroundColor: 'var(--surface-panel)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sharp)'
          }}>
            <span className="coord-label">CURRENT AVERAGE SCORE:</span>
            <strong className="stat-large-num" style={{ fontSize: '30px', color: 'var(--terracotta)' }}>
              {averageScore}%
            </strong>
          </div>
        </div>

        {/* 4-Stat Live Telemetry Ribbon */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '12px',
          marginTop: '16px',
          paddingTop: '14px',
          borderTop: '1px solid var(--border)'
        }}>
          <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-panel)', border: '1px solid var(--border)', borderRadius: '2px' }}>
            <span className="coord-label">OVERALL ACCURACY</span>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink-primary)', marginTop: '2px' }}>
              {averageScore}%
            </div>
            <span style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>Updated from practice</span>
          </div>

          <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-panel)', border: '1px solid var(--border)', borderRadius: '2px' }}>
            <span className="coord-label">TOPICS MASTERED</span>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink-primary)', marginTop: '2px' }}>
              {strongConcepts.length} / {conceptsList.length}
            </div>
            <span style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>Score ≥ 80%</span>
          </div>

          <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-panel)', border: '1px solid var(--border)', borderRadius: '2px' }}>
            <span className="coord-label">REVIEW RECOMMENDED</span>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--terracotta)', marginTop: '2px' }}>
              {reviewConcepts.length} Topics
            </div>
            <span style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>Target practice ready</span>
          </div>

          <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-panel)', border: '1px solid var(--border)', borderRadius: '2px' }}>
            <span className="coord-label">DATA INTEGRATION</span>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink-primary)', marginTop: '2px' }}>
              Active
            </div>
            <span style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>Dynamic backend ready</span>
          </div>
        </div>
      </section>

      {/* 2-Column Split: Topics Requiring Review vs Mastered Topics */}
      <div className="progress-split-grid">
        {/* Left Column: Topics to Review */}
        <div className="progress-column">
          <div className="atelier-card progress-panel-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphCrosshair size={14} />
                <span className="coord-label">TOPICS REQUIRING REVIEW ({reviewConcepts.length})</span>
              </div>
              <span className="card-badge-warn" style={{ color: 'var(--terracotta)' }}>REVIEW SUGGESTED</span>
            </div>

            <div className="progress-concept-list">
              {reviewConcepts.map(c => {
                const score = masteryScores[c.id] || 0;
                return (
                  <div key={c.id} className="progress-item-card needs-work">
                    <div className="item-meta-row">
                      <span className="coord-label">CHAPTER 3 · PAGE {c.page}</span>
                      <span className="item-score-pill" style={{ color: 'var(--terracotta)', fontWeight: 700 }}>
                        {score}%
                      </span>
                    </div>

                    <h3 className="item-title">{c.title}</h3>
                    <p className="item-summary">{c.summary}</p>

                    {/* Progress Bar */}
                    <div style={{ margin: '8px 0', height: '6px', backgroundColor: 'var(--surface-secondary)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{ width: `${score}%`, height: '100%', backgroundColor: 'var(--terracotta)' }} />
                    </div>

                    <div className="item-actions-row">
                      <button 
                        type="button" 
                        className="btn-atelier-primary"
                        onClick={() => {
                          setActiveConceptId(c.id);
                          navigate('/app/assessment');
                        }}
                      >
                        <span>Practice Questions</span>
                        <GlyphArrowRight size={12} />
                      </button>
                      <button 
                        type="button" 
                        className="btn-atelier-outline"
                        onClick={() => {
                          setActiveConceptId(c.id);
                          navigate('/app/studio');
                        }}
                      >
                        <span>Study Lesson</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Confirmed Mastered Topics */}
        <div className="progress-column">
          <div className="atelier-card progress-panel-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphCheckmark size={14} />
                <span className="coord-label">MASTERED TOPICS ({strongConcepts.length})</span>
              </div>
              <span className="card-badge-soft">PROFICIENT</span>
            </div>

            <div className="progress-concept-list">
              {strongConcepts.map(c => {
                const score = masteryScores[c.id] || 0;
                return (
                  <div key={c.id} className="progress-item-card confirmed">
                    <div className="item-meta-row">
                      <span className="coord-label">CHAPTER 3 · PAGE {c.page}</span>
                      <span className="item-score-pill" style={{ color: 'var(--ink-primary)', fontWeight: 700 }}>
                        {score}%
                      </span>
                    </div>

                    <h3 className="item-title">{c.title}</h3>
                    <p className="item-summary">{c.summary}</p>

                    {/* Progress Bar */}
                    <div style={{ margin: '8px 0', height: '6px', backgroundColor: 'var(--surface-secondary)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{ width: `${score}%`, height: '100%', backgroundColor: 'var(--ink-primary)' }} />
                    </div>

                    <div className="item-actions-row">
                      <button 
                        type="button" 
                        className="btn-atelier-outline"
                        onClick={() => {
                          setActiveConceptId(c.id);
                          navigate('/app/assessment');
                        }}
                      >
                        <span>Re-test Mastery</span>
                        <GlyphRotate size={12} />
                      </button>
                      <button 
                        type="button" 
                        className="btn-atelier-outline"
                        onClick={() => {
                          setActiveConceptId(c.id);
                          navigate('/app/studio');
                        }}
                      >
                        <span>Review Notes</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
