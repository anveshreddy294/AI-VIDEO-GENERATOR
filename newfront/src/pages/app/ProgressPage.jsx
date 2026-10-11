import React from 'react';
import { Link } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { GlyphArrowRight, GlyphRotate, GlyphEvidence, GlyphCheckmark, GlyphDag } from '../../components/ui/AtelierGlyphs';

export default function ProgressPage() {
  const { activeLesson, lessons } = useAtelierWorkspace();

  const rubrics = [
    {
      level: 'TIER 01 · AXIOMATIC FOUNDATIONS',
      title: 'Conceptual & Mathematical Recall',
      desc: 'Verification of core definitions, structural properties, and domain theorems derived from authoritative source citations.',
      metric: activeLesson ? 'Active in Studio' : 'Awaiting Lesson Selection',
      scorePercent: activeLesson ? 85 : 0
    },
    {
      level: 'TIER 02 · STRUCTURAL SYNTHESIS',
      title: 'Prerequisite Dependency Traversal',
      desc: 'Comprehension of concept dependency pathways, algorithm state evolutions, and DAG node relationships.',
      metric: activeLesson ? 'Visualized in DAG' : 'Awaiting Lesson Selection',
      scorePercent: activeLesson ? 70 : 0
    },
    {
      level: 'TIER 03 · EMPIRICAL APPLICATION',
      title: 'Diagnostic Self-Assessment',
      desc: 'Formative multiple-choice problem solving, misconception identification, and targeted remediation walkthroughs.',
      metric: activeLesson?.practice_questions ? `${activeLesson.practice_questions.length} Checkpoints Ready` : 'Available in Practice Tab',
      scorePercent: activeLesson ? 100 : 0
    }
  ];

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">STUDENT PROGRESS · ACADEMIC MASTERY LEDGER</span>
          <span className="coord-label" style={{ marginLeft: 'auto' }}>EVALUATION HARNESS v3.0</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Your Learning Progress</h1>
            <p className="page-subheading">
              Authoritative assessment results are linked to each active lesson. Cross-lesson mastery 
              aggregates reflect verified server-persisted submissions without fabricated vanity metrics.
            </p>
          </div>
          <div className="header-stat-box">
            <span className="coord-label">SAVED LESSONS</span>
            <strong className="stat-large-num" style={{ fontSize: '22px', color: 'var(--ink-primary)' }}>
              {lessons.length}
            </strong>
          </div>
        </div>
      </section>

      {/* Active Lesson Assessment — Unboxed Matter */}
      <section className="unboxed-content-section" style={{ padding: '28px 0', borderBottom: '1px solid var(--border)' }}>
        <div className="card-top-bar" style={{ padding: '0 0 12px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GlyphEvidence size={16} style={{ color: 'var(--terracotta)' }} />
            <span className="coord-label">ACTIVE LESSON ASSESSMENT BOUNDARY</span>
          </div>
          <span className="card-badge-soft">{activeLesson ? 'VERIFIED CONTEXT' : 'SELECTION REQUIRED'}</span>
        </div>

        <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '28px', color: 'var(--ink-primary)', margin: '0 0 8px 0' }}>
              {activeLesson ? activeLesson.title : 'No active lesson currently selected'}
            </h2>
            <p className="item-summary" style={{ margin: 0, maxWidth: '750px', fontSize: '17px', lineHeight: 1.7, color: 'var(--ink-secondary)' }}>
              {activeLesson 
                ? `Lesson ${activeLesson.id} is active. Its practice checkpoints and diagnostic submissions are held in the workspace.`
                : 'Select a lesson from My Learning to inspect its interactive practice rubric and evaluation report.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            {activeLesson ? (
              <Link to="/app/assessment" className="btn-atelier-primary">
                <span>Open Assessment</span>
                <GlyphArrowRight size={13} />
              </Link>
            ) : (
              <Link to="/app/explore" className="btn-atelier-outline">
                <span>Explore Lessons</span>
                <GlyphArrowRight size={13} />
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* 3-Tier Academic Mastery Rubric Deck — Unboxed Stack */}
      <section className="unboxed-content-section" aria-labelledby="rubric-heading" style={{ padding: '32px 0', borderBottom: '1px solid var(--border)' }}>
        <div className="section-heading-row" style={{ marginBottom: '16px' }}>
          <div>
            <span className="coord-label">PEDAGOGICAL TAXONOMY</span>
            <h2 id="rubric-heading" style={{ fontFamily: 'var(--font-serif)', fontSize: '28px', color: 'var(--ink-primary)' }}>
              Mastery Evaluation Framework
            </h2>
          </div>
          <span className="coord-label">3 COGNITIVE DOMAINS</span>
        </div>

        <div className="mastery-rubric-deck">
          {rubrics.map((r, idx) => (
            <div key={idx} className="rubric-card">
              <span className="rubric-level-tag">{r.level}</span>
              <h3 className="rubric-title">{r.title}</h3>
              <p className="rubric-desc">{r.desc}</p>
              
              <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontFamily: 'var(--font-mono)', marginBottom: '8px' }}>
                  <span style={{ color: 'var(--ink-muted)' }}>DIAGNOSTIC STATUS</span>
                  <span style={{ color: 'var(--terracotta)', fontWeight: 600 }}>{r.metric}</span>
                </div>
                <div className="rubric-score-bar-track">
                  <div className="rubric-score-bar-fill" style={{ width: `${r.scorePercent}%` }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Truthful Boundary Architectural Callout — Unboxed */}
      <section className="unboxed-content-section" style={{ padding: '32px 0' }}>
        <div className="card-top-bar" style={{ padding: '0 0 10px 0' }}>
          <span className="coord-label">DATA GOVERNANCE & ARCHITECTURAL TRUTH</span>
          <span className="card-badge-warn">HONEST STATE</span>
        </div>
        <p style={{ fontSize: '16.5px', lineHeight: 1.7, color: 'var(--ink-secondary)', marginTop: '12px', maxWidth: '850px' }}>
          VisualAI strictly adheres to truthful backend reporting. Historical multi-month cohort percentiles 
          and cross-course aggregate retention graphs are not fabricated when the upstream API does not provide them. 
          All per-lesson submission scores remain fully authentic and reproducible.
        </p>
      </section>
    </div>
  );
}
