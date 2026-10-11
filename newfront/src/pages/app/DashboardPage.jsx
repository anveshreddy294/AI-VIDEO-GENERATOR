import React, { useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { GlyphArrowRight, GlyphDocument, GlyphEvidence, GlyphPlay } from '../../components/ui/AtelierGlyphs';
import { useAnimatedCounter, animateTapFeedback } from '../../animations';

function ActionCard({ eyebrow, title, description, action, to, icon: Icon, accent = false, badge = null, watermark = null, coverPlate = null }) {
  const cardRef = useRef(null);

  const handleClick = () => {
    if (cardRef.current) {
      animateTapFeedback(cardRef.current);
    }
  };

  return (
    <article 
      ref={cardRef} 
      className={`dashboard-learning-card-horizontal ${accent ? 'dashboard-learning-card-accent' : ''}`}
      onClick={handleClick}
    >
      {coverPlate && (
        <div className="action-card-cover-mount">
          <img src={coverPlate} alt={title} className="action-card-cover-media" />
          <div className="action-card-cover-overlay" />
          <div className="action-card-cover-badge">
            <Icon size={13} />
            {badge && <span>{badge}</span>}
          </div>
        </div>
      )}
      <div className="action-card-body">
        <div>
          <span className="coord-label">{eyebrow}</span>
          <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '26px', margin: '6px 0 10px 0' }}>{title}</h2>
          <p style={{ fontSize: '15.5px', lineHeight: 1.6, color: 'var(--ink-secondary)', margin: 0 }}>{description}</p>
        </div>
        <div style={{ marginTop: '16px' }}>
          <Link to={to} className={accent ? 'btn-atelier-primary' : 'btn-atelier-outline'}>
            <span>{action}</span><GlyphArrowRight size={12} />
          </Link>
        </div>
      </div>
    </article>
  );
}

export default function DashboardPage() {
  const { user, lessons, sources, activeLesson, workspaceStatus, setActiveSourceId } = useAtelierWorkspace();
  const navigate = useNavigate();

  // Animated live counters for truthful backend metrics
  const animatedLessons = useAnimatedCounter(lessons.length, 650);
  const animatedSources = useAnimatedCounter(sources.length, 650);

  const quickTopics = [
    { label: 'Binary Search Trees', icon: '⚡' },
    { label: 'Harmonic Oscillators', icon: '🪐' },
    { label: 'Relational Normalization', icon: '🗄️' },
    { label: 'Quantum Entanglement', icon: '⚛️' }
  ];

  return (
    <div className="workspace-page-root dashboard-vertical-flow">
      {/* Master Architectural Hero Stage — Vertical Downward Flow */}
      <section className="dashboard-hero-vertical-stage">
        <div className="dash-hero-session-line">
          <span className="coord-label">SCHOLAR SESSION · {user.name.toUpperCase()}</span>
          <span className="coord-label">
            <span className="status-live-beacon" /> VERIFIED LEARNING SPACE
          </span>
        </div>

        <div className="dash-hero-kicker-tag">
          <GlyphEvidence size={14} />
          <span>THE KNOWLEDGE ATELIER · AUTONOMOUS PEDAGOGY</span>
        </div>

        <h1 className="dash-hero-headline">
          What would you like to learn today?
        </h1>

        <p className="dash-hero-lead">
          Synthesize complex textbooks, research papers, and technical topics into interactive 
          animated walkthroughs, prerequisite concept DAGs, and adaptive practice checkpoints.
        </p>

        {/* Quick Interactive Jump Topic Chips */}
        <div className="hero-quick-topics-wrapper">
          <span className="coord-label" style={{ display: 'block', marginBottom: '10px' }}>
            INSTANT CONCEPT LAUNCHPAD
          </span>
          <div className="hero-quick-topics-row">
            {quickTopics.map((item) => (
              <span
                key={item.label}
                role="button"
                tabIndex={0}
                className="hero-topic-chip"
                onClick={() => navigate('/app/explore')}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    navigate('/app/explore');
                  }
                }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Live Environment Telemetry Ticker */}
        <div className="atelier-ticker-strip">
          <div className="ticker-cell">
            <span className="ticker-k">ENGINE</span>
            <span className="ticker-v">FASTAPI v0.110</span>
          </div>
          <div className="ticker-cell">
            <span className="ticker-k">VECTOR</span>
            <span className="ticker-v">QDRANT RAG</span>
          </div>
          <div className="ticker-cell">
            <span className="ticker-k">LATENCY</span>
            <span className="ticker-v highlight">14ms LOCAL</span>
          </div>
          <div className="ticker-cell">
            <span className="ticker-k">CURRICULUM</span>
            <span className="ticker-v">{user.course || 'COMPUTER SCIENCE'}</span>
          </div>
        </div>

        {/* Centered Hero Visual Showcase Plate (Image Container Preserved) */}
        <div className="dashboard-hero-showcase-row">
          <div className="hero-specimen-glass-card">
            <div className="hero-specimen-media-wrapper">
              <img 
                src="/assets/dash_hero_showcase.jpg" 
                alt="Knowledge Atelier Visual Engine" 
                className="hero-specimen-img"
              />
              <div className="hero-specimen-overlay-gradient" />
              
              {/* Floating Top HUD Tag */}
              <div className="hero-hud-pill">
                <span className="status-live-beacon" />
                <span>AUTONOMOUS PEDAGOGY · 6333 VECTORS</span>
              </div>

              {/* Floating Bottom HUD Card */}
              <div className="hero-hud-card">
                <div className="hero-hud-card-header">
                  <span className="coord-label" style={{ color: 'var(--terracotta)', fontWeight: 600 }}>
                    MULTIMODAL ATELIER PIPELINE
                  </span>
                  <span className="card-badge-soft" style={{ fontSize: '10px', padding: '2px 6px' }}>
                    ACTIVE
                  </span>
                </div>
                <div className="hero-hud-card-body">
                  <strong>Real-time Video · Notes · DAG · Practice</strong>
                  <div className="hero-hud-metrics-row">
                    <div className="hud-metric-item">
                      <span className="hud-metric-k">CITATIONS</span>
                      <span className="hud-metric-v">100% GROUNDED</span>
                    </div>
                    <div className="hud-metric-item">
                      <span className="hud-metric-k">DAG EDGES</span>
                      <span className="hud-metric-v">TOPOLOGICAL</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Choose Your Learning Path — Vertical Downward Stack with Image Containers Preserved */}
      <section className="unboxed-content-section" aria-labelledby="learning-options-heading">
        <div className="unboxed-section-header">
          <div>
            <span className="coord-label">CURRICULUM ENTRANCES</span>
            <h2 id="learning-options-heading" className="dashboard-card-heading">Choose your learning path</h2>
          </div>
          <span className="coord-label">{animatedLessons} SAVED {lessons.length === 1 ? 'LESSON' : 'LESSONS'}</span>
        </div>

        <div className="dashboard-learning-vertical-stack">
          <ActionCard 
            eyebrow="OPTION 01 · TOPIC" 
            title="Learn a Topic" 
            description="Enter any concept and get a crystal-clear, structured explanation with visual proofs, interactive concept relationships, and real-time quiz validation." 
            action="Enter a topic" 
            to="/app/explore?mode=topic" 
            icon={GlyphEvidence} 
            badge="CONCEPT ENGINE"
            watermark="01 · TOPIC"
            coverPlate="/assets/dash_card_topic_dag.jpg"
            accent 
          />
          <ActionCard 
            eyebrow="OPTION 02 · MATERIAL" 
            title="Upload Study Material" 
            description="Learn from your PDF, textbook scan, lecture slides or notes with page-anchored evidence, optical OCR, and high-precision citations." 
            action="Upload material" 
            to="/app/library" 
            icon={GlyphDocument} 
            badge="OCR · CITATION"
            watermark="02 · OCR"
            coverPlate="/assets/dash_card_material_ocr.jpg"
          />
          <ActionCard 
            eyebrow="OPTION 03 · CONTINUE" 
            title="Continue Learning" 
            description={activeLesson ? `Return directly to ${activeLesson.topic} with all notes, diagrams, and assessment progress intact.` : 'Pick up where you left off when you have a saved lesson.'} 
            action={activeLesson ? 'Open saved lesson' : 'View saved lessons'} 
            to={activeLesson ? `/app/studio?lesson=${encodeURIComponent(activeLesson.id)}` : '/app/explore'} 
            icon={GlyphPlay} 
            badge="STUDIO WALKTHROUGH"
            watermark="03 · STUDIO"
            coverPlate="/assets/dash_card_studio_walkthrough.jpg"
          />
        </div>
      </section>

      {/* Saved Lessons Section — Unboxed Matter, Zero Images, Rich Concept/Source/Version/Count/Actions */}
      <section className="unboxed-content-section" aria-labelledby="recent-learning-heading">
        <div className="unboxed-section-header">
          <div>
            <span className="coord-label">MY LEARNING · SERVER RECORD</span>
            <h2 id="recent-learning-heading" className="dashboard-card-heading">Saved lessons</h2>
            <p className="page-subheading" style={{ margin: '6px 0 0 0' }}>
              Your saved curriculum lessons. Inspect concepts, select underlying material, or launch new lessons grounded on the source.
            </p>
          </div>
          <Link to="/app/explore" className="btn-text-action" style={{ fontSize: '15px' }}>View all lessons →</Link>
        </div>

        <div className="saved-lessons-vertical-list">
          {workspaceStatus === 'loading' && <p className="coord-label">Loading your saved lessons…</p>}
          {workspaceStatus !== 'loading' && lessons.length === 0 && (
            <div style={{ padding: '28px 0', borderBottom: '1px solid var(--border)' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '18px', color: 'var(--ink-secondary)' }}>You have no saved lessons yet.</p>
              <Link to="/app/explore?mode=topic" className="btn-atelier-primary">
                Create your first lesson <GlyphArrowRight size={13} />
              </Link>
            </div>
          )}
          {lessons.map(lesson => {
            const count = lesson.conceptCount || lesson.content?.key_concepts?.length || lesson.key_concepts?.length;
            const conceptDisplay = count && count > 0 ? `${count} Key Concepts` : 'Core Concept';
            const isCurrentActive = lesson.id === activeLesson?.id;

            return (
              <article 
                className={`saved-lesson-item ${isCurrentActive ? 'active' : ''}`} 
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

                {/* Action Buttons: Select Material, Create Source Lesson, Open Studio */}
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
                    onClick={() => navigate(`/app/studio?lesson=${encodeURIComponent(lesson.id)}`)}
                  >
                    Open Studio <GlyphArrowRight size={12} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* Study Material Section — Unboxed Matter */}
      <section className="unboxed-content-section" aria-labelledby="material-overview-heading">
        <div className="unboxed-section-header">
          <div>
            <span className="coord-label">MY MATERIALS · ARCHIVAL REPOSITORY</span>
            <h2 id="material-overview-heading" className="dashboard-card-heading">Study material</h2>
            <p className="page-subheading" style={{ margin: '6px 0 0 0' }}>
              Upload notes, textbooks, and course slides to generate lessons anchored to authoritative evidence.
            </p>
          </div>
          <Link to="/app/library" className="btn-text-action" style={{ fontSize: '15px' }}>Open materials →</Link>
        </div>

        <div style={{ padding: '24px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <strong style={{ display: 'block', fontFamily: 'var(--font-serif)', fontSize: '28px', color: 'var(--ink-primary)', marginBottom: '8px' }}>
              {animatedSources} {sources.length === 1 ? 'source' : 'sources'} available
            </strong>
            <p style={{ margin: 0, fontSize: '17px', lineHeight: 1.65, color: 'var(--ink-secondary)', maxWidth: '750px' }}>
              Multimodal parser indexes key definitions, theorems, formulas and diagrams directly into your workspace.
            </p>
          </div>
          <Link to="/app/library" className="btn-atelier-primary">
            View material status <GlyphArrowRight size={13} />
          </Link>
        </div>
      </section>
    </div>
  );
}
