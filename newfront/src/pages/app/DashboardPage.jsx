import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { GlyphArrowRight, GlyphDocument, GlyphEvidence } from '../../components/ui/AtelierGlyphs';
import { LoadingContent } from '../../components/ui/Skeleton';
import { toUserMessage } from '../../services/api/errors';

export default function DashboardPage() {
  const { user, lessons, sources, activeLesson, workspaceStatus, workspaceError } = useAtelierWorkspace();
  const navigate = useNavigate();

  return (
    <div className="workspace-page-root">
      <section className="modern-dashboard-hero">
        <div className="dash-hero-session-line">
          <span className="coord-label">WELCOME BACK, {user.name.toUpperCase()}</span>
        </div>
        <h1>What would you like to learn today?</h1>
        <p>Choose a topic, bring your own study material, or continue a lesson already saved to your workspace.</p>
      </section>

      <section className="modern-dashboard-actions" aria-label="Learning options">
        <article className="modern-action-primary">
          <div><span className="coord-label">START WITH A QUESTION</span><h2>Learn a topic</h2><p>Enter a concept and receive a clear explanation with concepts, examples, notes, practice and video in one workspace.</p></div>
          <Link to="/app/explore?mode=topic" className="btn-atelier-primary">Enter a topic <GlyphArrowRight size={12} /></Link>
        </article>
        <div className="modern-action-secondary">
          <div><span className="coord-label">BRING YOUR MATERIAL</span><h2>Upload study material</h2><p>Use a supported PDF, image or study note. We will show its real processing state.</p></div>
          <Link to="/app/library" className="btn-atelier-outline">Open My Materials <GlyphDocument size={12} /></Link>
        </div>
      </section>

      <section className="modern-dashboard-section" aria-labelledby="continue-heading">
        <div className="modern-dashboard-section-header"><div><span className="coord-label">RETURN TO YOUR WORK</span><h2 id="continue-heading">Continue learning</h2></div><Link to="/app/explore" className="btn-text-action">View all lessons</Link></div>
        <div className="modern-dashboard-list">
          {workspaceStatus === 'loading' && <LoadingContent label="Loading saved lessons…" />}
          {workspaceError && <p role="alert">{toUserMessage(workspaceError)}</p>}
          {workspaceStatus === 'ready' && lessons.length === 0 && <div style={{ padding: '18px 0' }}><p style={{ color: 'var(--ink-secondary)', marginBottom: '12px' }}>No saved lessons yet. Your first lesson can start with a topic above.</p><Link to="/app/explore?mode=topic" className="btn-atelier-outline">Create your first lesson <GlyphArrowRight size={12} /></Link></div>}
          {lessons.slice(0, 5).map(lesson => <button type="button" className={`modern-dashboard-list-row ${lesson.id === activeLesson?.id ? 'active' : ''}`} key={lesson.id} onClick={() => navigate(`/app/studio?lesson=${encodeURIComponent(lesson.id)}&tab=learn`)}><span><strong>{lesson.title}</strong><small>{lesson.source_id ? 'From your material' : 'Topic lesson'}{lesson.status ? ` · ${lesson.status.replaceAll('_', ' ')}` : ''}</small></span><GlyphArrowRight size={14} /></button>)}
        </div>
      </section>

      <section className="modern-dashboard-section" aria-labelledby="material-summary-heading">
        <div className="modern-dashboard-section-header"><div><span className="coord-label">YOUR MATERIALS</span><h2 id="material-summary-heading">Study library</h2></div><Link to="/app/library" className="btn-text-action">View materials</Link></div>
        <div className="modern-dashboard-list">{workspaceStatus === 'loading' ? <LoadingContent label="Loading materials…" lines={2} /> : <div className="modern-dashboard-list-row"><span><strong>{sources.length} saved {sources.length === 1 ? 'material' : 'materials'}</strong><small>Open My Materials to check processing status or start a lesson.</small></span><GlyphDocument size={15} /></div>}</div>
      </section>
    </div>
  );
}
