import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphPlay, 
  GlyphPause, 
  GlyphEvidence, 
  GlyphDocument, 
  GlyphCheckmark, 
  GlyphArrowRight, 
  GlyphCrosshair,
  GlyphLayers,
  GlyphSearch 
} from '../../components/ui/AtelierGlyphs';

export default function LearningStudioPage() {
  const { 
    activeSource, 
    activeConcept, 
    setActiveConceptId, 
    allConcepts 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackProgress, setPlaybackProgress] = useState(38);
  const [notesDepth, setNotesDepth] = useState('standard'); // concise | standard | detailed
  const [activeTab, setActiveTab] = useState('notes'); // notes | ask | mindmap
  const [askQuestion, setAskQuestion] = useState('');
  const [chatLog, setChatLog] = useState([
    {
      sender: 'user',
      text: 'Why does the relational model mathematically forbid NULL values in primary key attributes?'
    },
    {
      sender: 'atelier',
      text: 'Primary keys enforce the Entity Integrity Rule. If a primary key attribute were allowed to be NULL, the database engine could not distinguish between an entity that does not exist and an entity whose identity is merely unknown. In relational calculus, tuples represent distinct physical entities; without non-null uniqueness, relational joins become non-deterministic.',
      citation: 'Database Systems v2, Chapter 3, Page 7 · Bounding Box [142, 288, 480, 320]'
    }
  ]);

  const handleAskSubmit = (e) => {
    e.preventDefault();
    if (!askQuestion.trim()) return;

    const userQ = askQuestion.trim();
    setChatLog(prev => [
      ...prev,
      { sender: 'user', text: userQ },
      { 
        sender: 'atelier', 
        text: `Based on verified curriculum in ${activeSource.name} (Page ${activeConcept.page}): The concept of "${activeConcept.title}" establishes that ${activeConcept.summary.toLowerCase()} All relational constraints are verified against algebraic domain specifications.`,
        citation: `${activeSource.filename}, Page ${activeConcept.page} · Sub-pixel OCR Invariant`
      }
    ]);
    setAskQuestion('');
  };

  return (
    <div className="workspace-page-root">
      {/* Studio Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">STAGE D · MULTIMODAL LEARNING STUDIO</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">{activeConcept.title}</h1>
            <p className="page-subheading">
              Grounded curriculum delivery from <strong>{activeSource.name}</strong> · Section Page {activeConcept.page}
            </p>
          </div>
          <div className="header-actions">
            <button 
              type="button" 
              className="btn-atelier-outline"
              onClick={() => navigate('/app/explore')}
            >
              <span>View Topic Map</span>
            </button>
            <button 
              type="button" 
              className="btn-atelier-primary"
              onClick={() => navigate('/app/assessment')}
            >
              <span>Practice Concept</span>
              <GlyphCheckmark size={12} />
            </button>
          </div>
        </div>

        {/* Concept Selector Pills */}
        <div className="studio-concept-selector-strip">
          <span className="coord-label">SELECT CONCEPT:</span>
          {Object.values(allConcepts).map(c => (
            <button
              key={c.id}
              type="button"
              className={`concept-pill-btn ${activeConcept.id === c.id ? 'active' : ''}`}
              onClick={() => setActiveConceptId(c.id)}
            >
              {c.title}
            </button>
          ))}
        </div>
      </section>

      {/* Main Studio 2-Column Split */}
      <div className="studio-workspace-grid">
        {/* Left Column: Visual Demonstration Player Viewport */}
        <div className="studio-canvas-column">
          <div className="atelier-card studio-media-stage-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphPlay size={13} />
                <span className="coord-label">LESSON VIDEO PLAYER</span>
              </div>
              <span className="card-badge-soft">HD VIDEO LESSON</span>
            </div>

            {/* Contained Media Stage Frame */}
            <div className="studio-stage-frame">
              <img 
                src={activeConcept.plateImage} 
                alt={activeConcept.title} 
                className="studio-video-poster" 
              />
              
              {/* Center Play Button Overlay */}
              <div className="studio-play-overlay">
                <button 
                  type="button" 
                  className="stage-play-button"
                  onClick={() => setIsPlaying(!isPlaying)}
                  aria-label={isPlaying ? 'Pause Lesson' : 'Play Lesson'}
                >
                  {isPlaying ? <GlyphPause size={20} /> : <GlyphPlay size={20} />}
                </button>
              </div>

              {/* In-Frame Formula Bar */}
              <div className="stage-formula-overlay">
                <span className="coord-label">KEY TAKEAWAY:</span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', fontWeight: 600, color: 'var(--ink-inverse)' }}>
                  Every record must have a unique, non-null primary key
                </span>
              </div>
            </div>

            {/* Video Scrubber & Playback Controls */}
            <div className="studio-controls-bar">
              <button 
                type="button" 
                className="control-icon-btn"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <GlyphPause size={14} /> : <GlyphPlay size={14} />}
              </button>

              <div className="scrubber-track-container">
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={playbackProgress}
                  onChange={(e) => setPlaybackProgress(Number(e.target.value))}
                  className="studio-scrubber-slider"
                />
              </div>

              <span className="playback-timestamp mono">
                00:{playbackProgress < 10 ? `0${playbackProgress}` : playbackProgress} / 01:25
              </span>

              <span className="quality-pill">HD 1080P</span>
            </div>

            {/* Optical Source Grounding Strip */}
            <div className="studio-grounding-spec-strip">
              <GlyphEvidence size={14} />
              <span>Textbook Citation: <strong>{activeSource.name}</strong> (Chapter 3, Page {activeConcept.page})</span>
              <span className="verified-tag">100% VERIFIED</span>
            </div>
          </div>
        </div>

        {/* Right Column: Multi-tab Interactive Inspection Drawer */}
        <div className="studio-drawer-column">
          <div className="atelier-card studio-drawer-card">
            {/* Drawer Tab Header */}
            <div className="drawer-tabs-strip">
              <button 
                type="button" 
                className={`drawer-tab-btn ${activeTab === 'notes' ? 'active' : ''}`}
                onClick={() => setActiveTab('notes')}
              >
                ✍️ AI Study Notes
              </button>
              <button 
                type="button" 
                className={`drawer-tab-btn ${activeTab === 'ask' ? 'active' : ''}`}
                onClick={() => setActiveTab('ask')}
              >
                Ask Questions ({chatLog.length})
              </button>
              <button 
                type="button" 
                className={`drawer-tab-btn ${activeTab === 'mindmap' ? 'active' : ''}`}
                onClick={() => setActiveTab('mindmap')}
              >
                Topic Outline
              </button>
            </div>

            {/* TAB 1: AUTHENTIC HANDWRITTEN AI LESSON NOTES */}
            {activeTab === 'notes' && (
              <div className="drawer-tab-content">
                {/* Handwritten Notebook Sheet */}
                <div className="handwritten-notebook-page">
                  {/* Left Red Margin Line */}
                  <div className="notebook-red-margin" />

                  {/* Top Notebook Header Line */}
                  <div className="notebook-header-line">
                    <span className="notebook-subject-tag">
                      CS 304 · STUDY NOTES · CHAPTER 3
                    </span>
                    <span className="notebook-date-tag">
                      OCT 9, 2026 · PG {activeConcept.page}
                    </span>
                  </div>

                  {/* Handwritten Title */}
                  <h3 className="notebook-title-handwritten">
                    Why {activeConcept.title} Matters
                  </h3>

                  {/* Handwritten Body & Bullets */}
                  <div className="notebook-body-handwritten">
                    <p>
                      In relational databases, every single table needs an unambiguous way to identify each row.
                      Think of it like a student roll number or passport number!
                    </p>

                    <div className="notebook-bullet-item">
                      <span>•</span>
                      <div>
                        <strong>Rule #1 (Uniqueness): </strong>
                        No two rows can share the exact same key.
                        <mark className="highlighter-pen">Every record must be distinct.</mark>
                      </div>
                    </div>

                    <div className="notebook-bullet-item">
                      <span>•</span>
                      <div>
                        <strong>Rule #2 (Non-Null Mandate): </strong>
                        A primary key <mark className="highlighter-pen-terracotta">can NEVER be NULL (empty)</mark>.
                        If identity is missing, the database cannot safely locate or link the record.
                      </div>
                    </div>

                    <div className="notebook-bullet-item">
                      <span>•</span>
                      <div>
                        <strong>Real-World Example: </strong>
                        In a <code>Students</code> table, two people can be named "Alex Smith",
                        but their <code>student_id</code> (e.g. 104829 vs 104830) keeps them separate.
                      </div>
                    </div>

                    {/* Handwritten Sticky Note Callout */}
                    <div className="notebook-sticky-note">
                      📌 <strong>Exam Tip:</strong> If an exam asks whether a primary key column can hold a NULL value,
                      the answer is ALWAYS <strong>NO</strong>! That is the core rule of Entity Integrity.
                    </div>

                    <div className="notebook-bullet-item">
                      <span>•</span>
                      <div>
                        <strong>Connecting Tables: </strong>
                        Other tables (like <code>Enrollments</code> or <code>Grades</code>) use this primary key
                        as a <mark className="highlighter-pen">Foreign Key</mark> to link records without copying all student details.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: ASK THE ATELIER */}
            {activeTab === 'ask' && (
              <div className="drawer-tab-content">
                <div className="ask-chat-history">
                  {chatLog.map((msg, index) => (
                    <div key={index} className={`chat-message-bubble ${msg.sender}`}>
                      <div className="message-header">
                        <span className="coord-label">{msg.sender === 'user' ? 'STUDENT QUESTION' : 'ATELIER CITATION ENGINE'}</span>
                      </div>
                      <p className="message-text">{msg.text}</p>
                      {msg.citation && (
                        <div className="message-citation">
                          <GlyphEvidence size={12} />
                          <span>{msg.citation}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <form onSubmit={handleAskSubmit} className="ask-input-form">
                  <div className="ask-input-row">
                    <input 
                      type="text" 
                      placeholder={`Ask anything about ${activeConcept.title}...`}
                      value={askQuestion}
                      onChange={(e) => setAskQuestion(e.target.value)}
                      className="atelier-text-input"
                    />
                    <button type="submit" className="btn-atelier-primary">
                      <span>Query</span>
                      <GlyphArrowRight size={12} />
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* TAB 3: STRUCTURAL MIND MAP */}
            {activeTab === 'mindmap' && (
              <div className="drawer-tab-content">
                <div className="mindmap-container">
                  <div className="mindmap-root-node">
                    <span className="coord-label">SCHEMA ROOT</span>
                    <strong>{activeSource.name}</strong>
                  </div>
                  <div className="mindmap-branches">
                    {Object.values(allConcepts).map(c => (
                      <div 
                        key={c.id} 
                        className={`mindmap-branch-node ${c.id === activeConcept.id ? 'active' : ''}`}
                        onClick={() => setActiveConceptId(c.id)}
                      >
                        <span className="branch-dot" />
                        <span className="branch-title">{c.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
