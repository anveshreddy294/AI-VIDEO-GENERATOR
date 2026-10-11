import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { toUserMessage } from '../../services/api/errors';
import { humanSourceStatus } from '../../services/api/adapters';
import { GlyphArrowRight, GlyphCheckmark, GlyphDag, GlyphDocument } from '../../components/ui/AtelierGlyphs';
import { useAnimatedCounter, animateTapFeedback } from '../../animations';

const SUGGESTED_TOPICS = [
  'Relational Normalization',
  'Harmonic Oscillators',
  'Cellular Respiration',
  'Bayes Theorem',
  'Quantum Entanglement',
  'Graph Traversal'
];

export default function TopicExplorerPage() {
  const {
    sources, lessons, activeSource, activeLesson, createLesson, loadLesson,
    setActiveSourceId, setActiveLessonId, workspaceStatus
  } = useAtelierWorkspace();
  const navigate = useNavigate();
  const [topic, setTopic] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);

  const handleCreate = async event => {
    event.preventDefault();
    if (!topic.trim()) return;
    setIsCreating(true);
    setError(null);
    try {
      const selectedSource = sources.find(source => source.id === sourceId);
      const lesson = await createLesson({
        topic,
        sourceId: selectedSource?.id,
        sourceVersion: selectedSource?.version
      });
      navigate(`/app/studio?lesson=${encodeURIComponent(lesson.id)}`);
    } catch (requestError) {
      setError(toUserMessage(requestError));
    } finally {
      setIsCreating(false);
    }
  };

  const openLesson = async lesson => {
    setActiveLessonId(lesson.id);
    try {
      await loadLesson(lesson.id);
      navigate('/app/studio');
    } catch (requestError) {
      setError(toUserMessage(requestError));
    }
  };

  const animatedLessons = useAnimatedCounter(lessons.length, 600);

  return (
    <div className="workspace-page-root dashboard-vertical-flow">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">MY LEARNING · SERVER-SYNCHRONIZED CURRICULUM</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">My Learning</h1>
            <p className="page-subheading">
              Start a topic lesson or continue one you have already saved. All lessons are grounded to real concepts and verified citations.
            </p>
          </div>
          <div className="header-stat-tag">
            <span className="coord-label">LESSONS ON SERVER:</span>
            <strong style={{ fontSize: '24px', color: 'var(--ink-primary)' }}>{animatedLessons}</strong>
          </div>
        </div>
      </section>

      {/* Section 1: Learn a Topic — Full Width Unboxed Content Matter */}
      <section className="unboxed-content-section" aria-labelledby="learn-topic-heading">
        <div className="unboxed-section-header">
          <div>
            <span className="coord-label">CREATE NEW LESSON</span>
            <h2 id="learn-topic-heading" className="dashboard-card-heading">What would you like to learn?</h2>
            <p className="page-subheading" style={{ margin: '4px 0 0 0' }}>
              Enter any concept name to generate an authoritative explanation, flowchart DAG, and practice assessment.
            </p>
          </div>
        </div>

        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '880px' }}>
          <div>
            <label className="field-label" htmlFor="lesson-topic">Concept Topic</label>
            <input 
              id="lesson-topic" 
              className="atelier-input" 
              value={topic} 
              onChange={event => setTopic(event.target.value)} 
              placeholder="e.g. Binary Search Trees" 
              maxLength={240} 
              required 
            />
          </div>

          <div className="topic-suggestions-strip" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '4px 0' }}>
            <span className="coord-label" style={{ alignSelf: 'center', marginRight: '4px' }}>QUICK PICKS:</span>
            {SUGGESTED_TOPICS.map(item => (
              <span
                key={item}
                role="button"
                tabIndex={0}
                className="hero-topic-chip"
                style={{
                  borderColor: topic === item ? 'var(--terracotta)' : 'var(--border)',
                  backgroundColor: topic === item ? 'var(--terracotta-subtle)' : 'var(--canvas)'
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setTopic(item);
                  }
                }}
                onClick={e => {
                  animateTapFeedback(e.currentTarget);
                  setTopic(item);
                }}
              >
                {item}
              </span>
            ))}
          </div>

          <div>
            <label className="field-label" htmlFor="lesson-source">Optional: learn from one of your materials</label>
            <select 
              id="lesson-source" 
              className="atelier-input" 
              value={sourceId} 
              onChange={event => { 
                setSourceId(event.target.value); 
                setActiveSourceId(event.target.value || null); 
              }}
            >
              <option value="">Topic-only lesson</option>
              {sources.filter(source => source.contentReady).map(source => (
                <option key={source.id} value={source.id}>
                  {source.filename} · v{source.version}
                </option>
              ))}
            </select>
            <p className="coord-label" style={{ marginTop: '8px', lineHeight: 1.5 }}>
              Choose Topic-only for an ungrounded concept explanation, or select material after it has finished processing.
            </p>
          </div>

          {error && (
            <div className="signin-disclaimer-box" role="alert">
              <p>{error}</p>
            </div>
          )}

          <div>
            <button 
              type="submit" 
              className="btn-atelier-primary" 
              disabled={isCreating}
            >
              <span>{isCreating ? 'Preparing your lesson…' : 'Generate Lesson'}</span>
              <GlyphArrowRight size={12} />
            </button>
          </div>
        </form>
      </section>

      {/* Section 2: Current Active Lesson (if selected) — Full Width Unboxed */}
      {activeLesson && (
        <section className="unboxed-content-section" aria-labelledby="current-lesson-heading">
          <div className="unboxed-section-header">
            <div>
              <span className="coord-label">ACTIVE WORKSPACE LESSON</span>
              <h2 id="current-lesson-heading" className="dashboard-card-heading">{activeLesson.topic}</h2>
              <p className="coord-label" style={{ marginTop: '4px' }}>
                LESSON ID {activeLesson.id} {activeLesson.source_id ? `· GROUNDED TO SOURCE ${activeLesson.source_id}` : '· TOPIC ONLY'}
              </p>
            </div>
            <button 
              type="button" 
              className="btn-atelier-primary" 
              onClick={() => navigate('/app/studio')}
            >
              Open Learning Studio <GlyphArrowRight size={12} />
            </button>
          </div>
          <p style={{ fontSize: '16.5px', lineHeight: 1.7, color: 'var(--ink-secondary)', maxWidth: '880px', margin: 0 }}>
            {activeLesson.content?.explanation || 'The server returned verified learning material for this lesson.'}
          </p>
        </section>
      )}

      {/* Section 3: Saved Lessons / Continue Learning — Full Width Unboxed Matter, Zero Images */}
      <section className="unboxed-content-section" aria-labelledby="continue-learning-heading">
        <div className="unboxed-section-header">
          <div>
            <span className="coord-label">SAVED LESSONS ARCHIVE</span>
            <h2 id="continue-learning-heading" className="dashboard-card-heading">Continue Learning</h2>
            <p className="page-subheading" style={{ margin: '4px 0 0 0' }}>
              Your server-persisted curriculum. Choose any lesson to resume notes, flowchart DAG, and practice questions.
            </p>
          </div>
        </div>

        <div className="saved-lessons-vertical-list">
          {workspaceStatus === 'loading' && <p className="coord-label">Loading lessons…</p>}
          {workspaceStatus !== 'loading' && lessons.length === 0 && (
            <p className="coord-label">No saved lessons yet. Start with a topic above.</p>
          )}

          {lessons.map(lesson => {
            const count = lesson.conceptCount || lesson.content?.key_concepts?.length || lesson.key_concepts?.length;
            const conceptDisplay = count && count > 0 ? `${count} Key Concepts` : 'Core Concept';
            const isSelected = lesson.id === activeLesson?.id;

            return (
              <article 
                className={`saved-lesson-item ${isSelected ? 'active' : ''}`} 
                key={lesson.id}
              >
                <div className="saved-lesson-header-line">
                  <span className="coord-label">LESSON {lesson.id.slice(0, 8)}</span>
                  <span className="coord-label" style={{ color: 'var(--evergreen)', fontWeight: 600 }}>
                    {lesson.status || 'READY TO LEARN'}
                  </span>
                </div>

                <h3 className="saved-lesson-title">
                  {lesson.title}
                </h3>

                {/* Metadata Grid: Concept Name, Source ID, Version, Concept Count */}
                <div className="saved-lesson-meta-grid">
                  <div className="saved-lesson-meta-cell">
                    <span className="meta-label">CONCEPT NAME</span>
                    <span className="meta-value">{lesson.topic || lesson.title}</span>
                  </div>
                  <div className="saved-lesson-meta-cell">
                    <span className="meta-label">SOURCE ID</span>
                    <span className="meta-value mono">{lesson.source_id || 'Direct Topic (No Source)'}</span>
                  </div>
                  <div className="saved-lesson-meta-cell">
                    <span className="meta-label">VERSION</span>
                    <span className="meta-value">v{lesson.source_version || 1}</span>
                  </div>
                  <div className="saved-lesson-meta-cell">
                    <span className="meta-label">CONCEPT COUNT</span>
                    <span className="meta-value highlight">{conceptDisplay}</span>
                  </div>
                </div>

                {/* Actions: Select Material, Create Source Lesson, Open Studio button */}
                <div className="saved-lesson-actions-row">
                  {lesson.source_id ? (
                    <button 
                      type="button" 
                      className="btn-atelier-outline"
                      onClick={() => {
                        setActiveSourceId(lesson.source_id);
                        navigate('/app/library');
                      }}
                    >
                      Select Material
                    </button>
                  ) : null}

                  <button 
                    type="button" 
                    className="btn-atelier-outline"
                    onClick={() => {
                      if (lesson.source_id) setActiveSourceId(lesson.source_id);
                      navigate(`/app/explore?mode=source${lesson.source_id ? `&source=${lesson.source_id}` : ''}`);
                    }}
                  >
                    Create Source Lesson
                  </button>

                  <button 
                    type="button" 
                    className="btn-atelier-primary" 
                    onClick={() => openLesson(lesson)}
                  >
                    {lesson.title} · Open Studio <GlyphArrowRight size={12} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
