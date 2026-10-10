import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphArrowRight, 
  GlyphArrowUpRight, 
  GlyphDocument, 
  GlyphEvidence, 
  GlyphCheckmark,
  GlyphCrosshair,
  GlyphPlay
} from '../../components/ui/AtelierGlyphs';

export default function DashboardPage() {
  const { 
    user, 
    sources, 
    activeSource, 
    activeConcept, 
    masteryScores, 
    uploadSource 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const handleUploadSubmit = (e) => {
    e.preventDefault();
    if (!selectedFile) return;
    uploadSource(selectedFile);
    setSelectedFile(null);
    setUploadModalOpen(false);
  };

  return (
    <div className="workspace-page-root">
      {/* 1. PANORAMIC ATELIER COMMAND HERO STAGE */}
      <section className="dashboard-hero-stage">
        {/* Top Session Registration Line */}
        <div className="dash-hero-session-line">
          <span className="coord-label">
            STUDENT: {user.name.toUpperCase()} · {user.course || 'CS 304: DATABASE SYSTEMS'}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-live-beacon" />
            <span className="coord-label">100% EVIDENCE GROUNDED · STUDY SESSION ACTIVE</span>
          </div>
        </div>

        {/* 2-Column Command Hero Grid */}
        <div className="dash-hero-grid">
          {/* Left Column: Active Mission & Derivation Proposition */}
          <div className="dash-hero-proposition-col">
            <span className="dash-hero-kicker-tag">
              <GlyphEvidence size={13} />
              <span>ACTIVE STUDY TOPIC · UNIT 03</span>
            </span>

            <h1 className="dash-hero-headline">
              Mastering {activeConcept.title}
            </h1>

            <p className="dash-hero-lead">
              We have synthesized Chapter 3 of <em>{activeSource.name}</em> (Page {activeConcept.page}). 
              You have 1 topic to review on candidate key uniqueness before advancing to foreign keys.
            </p>

            <div className="dash-hero-actions-row">
              <Link to="/app/studio" className="btn-atelier-primary">
                <span>Watch Lesson Video</span>
                <GlyphArrowRight size={12} />
              </Link>
              <Link to="/app/assessment" className="btn-atelier-outline">
                <GlyphCrosshair size={12} />
                <span>Practice Questions</span>
              </Link>
              <Link to="/app/explore" className="btn-atelier-outline">
                <span>View Topic Roadmap</span>
                <GlyphArrowUpRight size={12} />
              </Link>
            </div>

            <div className="dash-hero-telemetry-strip">
              <div className="step-contract-item">
                <span className="contract-label">TEXTBOOK ANCHOR</span>
                <strong className="contract-val">Chapter 3, Page {activeConcept.page}</strong>
              </div>
              <div className="step-contract-item">
                <span className="contract-label">VERIFIED EVIDENCE</span>
                <strong className="contract-val">99% Textbook Source</strong>
              </div>
              <div className="step-contract-item">
                <span className="contract-label">KEY TAKEAWAY</span>
                <strong className="contract-val" style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 600 }}>
                  Primary keys must be unique & non-null
                </strong>
              </div>
            </div>
          </div>

          {/* Right Column: Levitating Observatory Stage Plate */}
          <div className="dash-hero-observatory-wrapper">
            <div className="dash-floating-chip-top">
              <GlyphCrosshair size={11} />
              <span>TOPIC LESSON PREVIEW</span>
            </div>

            <div className="dash-hero-observatory-card">
              <div className="mount-meta-header">
                <span className="coord-label">LESSON 04 · STUDY STUDIO</span>
                <span className="mount-status-dot">READY TO WATCH</span>
              </div>

              <div className="dash-observatory-media">
                <img 
                  src="/assets/study_desk_mac.jpg" 
                  alt="Student Study Workspace" 
                  className="dash-observatory-img floating-media-core" 
                />
              </div>

              <div className="dash-observatory-footer">
                <span>03:15 MIN · HD VIDEO LESSON</span>
                <Link to="/app/studio" className="mount-link-action">
                  <span>Open Video Studio</span>
                  <GlyphArrowRight size={10} />
                </Link>
              </div>
            </div>

            <div className="dash-floating-chip-bottom">
              <GlyphCheckmark size={11} />
              <span>RULE: Every row must have a unique identifier</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. SCHOLAR KPI TELEMETRY RIBBON */}
      <section className="dash-kpi-ribbon">
        <div className="dash-kpi-card">
          <span className="dash-kpi-label">VERIFIED MASTERY</span>
          <div className="dash-kpi-val">74%</div>
          <span className="dash-kpi-sub">+12% this session · 4/8 Topics</span>
        </div>

        <div className="dash-kpi-card">
          <span className="dash-kpi-label">EVIDENCE GROUNDING</span>
          <div className="dash-kpi-val">100%</div>
          <span className="dash-kpi-sub">Direct citations from textbook</span>
        </div>

        <div className="dash-kpi-card">
          <span className="dash-kpi-label">TOPICS TO REVIEW</span>
          <div className="dash-kpi-val" style={{ color: 'var(--terracotta)' }}>1 Alert</div>
          <span className="dash-kpi-sub" style={{ color: 'var(--terracotta)' }}>Review: Candidate Key Uniqueness</span>
        </div>

        <div className="dash-kpi-card">
          <span className="dash-kpi-label">LESSON MODULES</span>
          <div className="dash-kpi-val">4 Scenes</div>
          <span className="dash-kpi-sub">Interactive Lessons Ready</span>
        </div>
      </section>

      {/* 2. MAIN 2-COLUMN WORKSPACE GRID */}
      <div className="dash-grid-layout">
        {/* LEFT COLUMN: ACTIVE STUDY TARGET & REMEDIATION */}
        <div className="dash-left-column">
          {/* Active Study Target Card */}
          <div className="atelier-card study-target-card">
            <div className="card-top-bar">
              <span className="coord-label">ACTIVE STUDY TARGET</span>
              <span className="card-badge-soft">GROUNDED LESSON</span>
            </div>

            <div className="study-target-media-frame">
              <img src={activeSource.coverPlate} alt={activeSource.name} className="target-cover-img" />
              <div className="target-media-overlay">
                <span className="target-subject-tag">{activeSource.subject}</span>
                <span className="target-ver-tag">VERSION {activeSource.version} · READY</span>
              </div>
            </div>

            <div className="study-target-details">
              <span className="coord-label">{activeConcept.kicker}</span>
              <h2 className="target-concept-heading">{activeConcept.title}</h2>
              <p className="target-concept-summary">{activeConcept.summary}</p>

              <div className="target-grounding-spec">
                <GlyphEvidence size={14} className="spec-glyph" />
                <span>Verified Anchor: <strong>{activeSource.filename} · Page {activeConcept.page}</strong></span>
                <span className="spec-conf-pill">{activeSource.opticalConfidence} MATCH</span>
              </div>

              <div className="target-actions-strip">
                <button 
                  type="button" 
                  className="btn-atelier-primary"
                  onClick={() => navigate('/app/studio')}
                >
                  <span>Enter Concept Studio</span>
                  <GlyphArrowRight size={12} />
                </button>
                <button 
                  type="button" 
                  className="btn-atelier-outline"
                  onClick={() => navigate('/app/assessment')}
                >
                  <span>Practice Assessment</span>
                  <GlyphCheckmark size={12} />
                </button>
              </div>
            </div>
          </div>

          {/* Targeted Remediation Action Card */}
          <div className="atelier-card remediation-action-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphCrosshair size={14} />
                <span className="coord-label">TARGETED PEDAGOGICAL REMEDIATION</span>
              </div>
              <span className="card-badge-warn">MISCONCEPTION DETECTED</span>
            </div>

            <div className="remediation-body">
              <h3 className="remediation-target-title">Foreign Key Referential Integrity Nullability</h3>
              <p className="remediation-explanation">
                Diagnostic practice flagged a confusion between nullable optional foreign keys and 
                non-nullable entity integrity constraints.
              </p>
              <div className="remediation-dock-bar">
                <span className="remediation-est-time">ESTIMATED: 5-MIN MICRO-LESSON</span>
                <button 
                  type="button"
                  className="btn-atelier-terracotta"
                  onClick={() => navigate('/app/assessment')}
                >
                  <span>Launch Remediation</span>
                  <GlyphArrowRight size={12} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: KNOWLEDGE LIBRARY ACCESS & MASTERY BREAKDOWN */}
        <div className="dash-right-column">
          {/* Knowledge Library Sources List */}
          <div className="atelier-card library-quick-card">
            <div className="card-top-bar">
              <span className="coord-label">KNOWLEDGE SOURCES ({sources.length})</span>
              <button 
                type="button" 
                className="btn-text-action"
                onClick={() => setUploadModalOpen(true)}
              >
                + Ingest New Material
              </button>
            </div>

            <div className="sources-quick-list">
              {sources.map(src => (
                <div 
                  key={src.id}
                  className="source-row-item"
                  onClick={() => navigate('/app/library')}
                >
                  <div className="source-thumb-mount">
                    <img src={src.coverPlate} alt={src.name} className="source-thumb-img" />
                  </div>
                  <div className="source-row-meta">
                    <strong className="source-row-name">{src.name}</strong>
                    <div className="source-row-details">
                      <span>{src.format} · {src.pages} pgs</span>
                      <span>·</span>
                      <span className={`status-pill ${src.status.toLowerCase()}`}>{src.status}</span>
                    </div>
                  </div>
                  <GlyphArrowRight size={13} className="source-row-arrow" />
                </div>
              ))}
            </div>
          </div>

          {/* Honest Concept Mastery Overview */}
          <div className="atelier-card mastery-overview-card">
            <div className="card-top-bar">
              <span className="coord-label">HONEST CONCEPT MASTERY</span>
              <span className="card-badge-soft">DIAGNOSTIC TELEMETRY</span>
            </div>

            <div className="mastery-meters-list">
              {Object.entries(masteryScores).map(([cid, score]) => (
                <div key={cid} className="mastery-meter-row">
                  <div className="meter-label-row">
                    <span className="meter-concept-title">{cid.replace(/-/g, ' ').toUpperCase()}</span>
                    <strong className="meter-score-text">{score}%</strong>
                  </div>
                  <div className="meter-track">
                    <div 
                      className={`meter-fill ${score >= 80 ? 'strong' : score >= 60 ? 'moderate' : 'needs-work'}`}
                      style={{ width: `${score}%` }} 
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mastery-card-footer">
              <Link to="/app/progress" className="btn-atelier-outline" style={{ width: '100%', justifyContent: 'center' }}>
                <span>Inspect Full Mastery Roadmap</span>
                <GlyphArrowRight size={12} />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* UPLOAD MODAL */}
      {uploadModalOpen && (
        <div className="atelier-modal-backdrop">
          <div className="atelier-modal-dialog">
            <div className="modal-header-bar">
              <span className="coord-label">INGESTION PIPELINE · MULTIMODAL SOURCE</span>
              <button 
                type="button" 
                className="modal-close-btn"
                onClick={() => setUploadModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="modal-form">
              <h2 className="modal-title">Ingest Study Material</h2>
              <p className="modal-description">
                Upload a textbook PDF, lecture slides, or PNG schematics. The multimodal ingestion 
                engine extracts mathematical equations and anchors optical coordinates.
              </p>

              <div className="file-drop-mount">
                <input 
                  type="file" 
                  accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" 
                  required
                  id="source-file-input"
                  onChange={e => setSelectedFile(e.target.files?.[0])}
                  className="sr-only"
                />
                <label htmlFor="source-file-input" className="drop-mount-label">
                  <GlyphDocument size={28} className="drop-icon" />
                  <strong>{selectedFile ? selectedFile.name : 'Select curriculum document'}</strong>
                  <span className="coord-label">PDF, DOCX, PNG, JPG · MAX 25 MB</span>
                </label>
              </div>

              <div className="modal-actions-strip">
                <button 
                  type="button" 
                  className="btn-atelier-outline"
                  onClick={() => setUploadModalOpen(false)}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={!selectedFile}
                  className="btn-atelier-primary"
                >
                  <span>Start Pipeline Ingestion</span>
                  <GlyphArrowRight size={12} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
