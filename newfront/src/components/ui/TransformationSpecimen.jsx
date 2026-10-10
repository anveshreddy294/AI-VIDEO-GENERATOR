import React, { useState, useEffect } from 'react';
import { 
  GlyphDocument, 
  GlyphEvidence, 
  GlyphDag, 
  GlyphPlay, 
  GlyphPause,
  GlyphCheckmark, 
  GlyphArrowRight,
  GlyphCrosshair
} from './AtelierGlyphs';

export default function TransformationSpecimen() {
  const [activeStage, setActiveStage] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [isHovered, setIsHovered] = useState(false);

  const STAGES = [
    {
      id: 'A',
      badge: 'PHASE 01 · SOURCE INGESTION',
      title: 'Original Course Material',
      desc: 'Upload your textbooks, class slides, or lecture notes. VisualAI extracts verified text and formulas directly from your curriculum.',
      meta: 'SOURCE: Database Systems (Chapter 3) · Page 7',
      plate: '/assets/library_books_hall.jpg',
      annotation: 'ORIGINAL TEXTBOOK: § 3.2 PRIMARY KEYS'
    },
    {
      id: 'B',
      badge: 'PHASE 02 · TOPIC EXTRACTION',
      title: 'Core Concept Identification',
      desc: 'The platform identifies essential rules, key definitions, and examples, ensuring accurate study materials without hallucinations.',
      meta: 'FOUNDATION: Entity Integrity & Non-Null Rule',
      plate: '/assets/database_code_screen.jpg',
      annotation: 'KEY RULE: UNIQUE IDENTIFIER FOR EVERY ROW'
    },
    {
      id: 'C',
      badge: 'PHASE 03 · KNOWLEDGE ROADMAP',
      title: 'Structured Topic Map',
      desc: 'Topics are organized into clear prerequisite paths so you understand foundational basics before tackling advanced concepts.',
      meta: 'ROADMAP: Tables → Primary Keys → Foreign Keys → Normalization',
      plate: '/assets/student_studying.jpg',
      annotation: 'TOPIC ROADMAP: 8 CONNECTED LESSONS'
    },
    {
      id: 'D',
      badge: 'PHASE 04 · INTERACTIVE LESSONS',
      title: 'Video Lessons & Handwritten Notes',
      desc: 'Watch step-by-step video lessons and review authentic handwritten study notes designed for effortless understanding.',
      meta: 'LESSON: Visualizing Key Constraints in Practice',
      plate: '/assets/study_desk_mac.jpg',
      annotation: 'LESSON WALKTHROUGH: 3 MIN VIDEO'
    },
    {
      id: 'E',
      badge: 'PHASE 05 · PRACTICE & MASTERY',
      title: 'Diagnostic Practice Questions',
      desc: 'Solve realistic practice questions that pinpoint common mistakes and help you master the topic before exams.',
      meta: 'PRACTICE: Identifying Surrogate vs Candidate Keys',
      plate: '/assets/notebook_handwritten.jpg',
      annotation: 'PRACTICE CHECKPOINT: MOCK QUESTIONS READY'
    },
    {
      id: 'F',
      badge: 'PHASE 06 · PROGRESS & REVIEW',
      title: 'Score Tracking & Targeted Review',
      desc: 'Track your live topic scores and jump straight into focused reviews whenever a concept needs a quick refresher.',
      meta: 'PROGRESS: 74% Current Mastery · 1 Review Topic',
      plate: '/assets/library_books_hall.jpg',
      annotation: 'MASTERY ROADMAP: TARGETED REVIEW'
    }
  ];

  // Automatic slide progression every 4.5 seconds
  useEffect(() => {
    if (!isAutoPlaying || isHovered) return;

    const timer = setInterval(() => {
      setActiveStage(prev => (prev + 1) % STAGES.length);
    }, 4500);

    return () => clearInterval(timer);
  }, [isAutoPlaying, isHovered, activeStage]);

  const current = STAGES[activeStage];

  const handleManualSelect = (idx) => {
    setActiveStage(idx);
  };

  const handleNextPhase = () => {
    setActiveStage(prev => (prev + 1) % STAGES.length);
  };

  const togglePlayback = () => {
    setIsAutoPlaying(prev => !prev);
  };

  return (
    <div 
      className="transformation-specimen-widget"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Autonomous Progression Sequencer Status Bar */}
      <div className="transformation-sequencer-bar">
        <div className="sequencer-status-tag">
          <span className={`sequencer-pulse-dot ${!isAutoPlaying || isHovered ? 'paused' : ''}`} />
          <span>
            {isHovered 
              ? 'AUTONOMOUS CYCLE PAUSED (INSPECTING)' 
              : isAutoPlaying 
              ? 'AUTONOMOUS TOPIC PROGRESSION ACTIVE · 4.5S CADENCE' 
              : 'AUTOMATIC ROTATION PAUSED'}
          </span>
        </div>

        <button 
          type="button" 
          className="sequencer-control-btn"
          onClick={togglePlayback}
          title={isAutoPlaying ? 'Pause automatic topic progression' : 'Start automatic topic progression'}
        >
          {isAutoPlaying ? (
            <>
              <GlyphPause size={10} />
              <span>Pause Auto</span>
            </>
          ) : (
            <>
              <GlyphPlay size={10} />
              <span>Resume Auto</span>
            </>
          )}
        </button>
      </div>

      {/* Top Stage Sequencer Bar with Live Progress Indicators */}
      <div className="stage-selector-strip">
        {STAGES.map((s, idx) => {
          const isActive = activeStage === idx;
          return (
            <button
              key={s.id}
              type="button"
              className={`stage-select-btn ${isActive ? 'active' : ''}`}
              onClick={() => handleManualSelect(idx)}
            >
              <div className="stage-btn-top">
                <span className="stage-letter">{s.id}</span>
                {isActive && (
                  <span className="coord-label" style={{ fontSize: '8px', color: 'inherit' }}>
                    ACTIVE
                  </span>
                )}
              </div>
              <span className="stage-short-title">{s.title.split(' ')[0]}</span>
              
              {isActive && (
                <div className="stage-progress-track">
                  <div 
                    key={`progress-${idx}-${isAutoPlaying}-${isHovered}`}
                    className={`stage-progress-fill ${!isAutoPlaying || isHovered ? 'paused' : ''}`} 
                  />
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Main Specimen Display Grid */}
      <div className="transformation-display-grid">
        {/* Left: Contained Specimen Mount (Zero background overlaps!) */}
        <div className="specimen-mount-column">
          <div className="specimen-contained-card floating-stage-plate stage-entrance-anim" key={current.id}>
            <div className="specimen-plate-frame">
              <img 
                src={current.plate} 
                alt={current.title} 
                className="specimen-plate-image floating-media-core" 
              />
              <div className="specimen-plate-annotation-bar">
                <GlyphCrosshair size={13} className="crosshair-icon" />
                <span>{current.annotation}</span>
              </div>
            </div>
            <div className="specimen-caption-row">
              <span className="specimen-caption-meta">{current.meta}</span>
              <span className="specimen-index-tag">PHASE {activeStage + 1} / 6</span>
            </div>
          </div>
        </div>

        {/* Right: Technical Explanation & Actions */}
        <div className="transformation-meta-column stage-entrance-anim" key={`meta-${current.id}`}>
          <div>
            <div className="transformation-kicker-row">
              <span className="coord-label">{current.badge}</span>
            </div>

            <h3 className="transformation-stage-title">{current.title}</h3>
            
            <p className="transformation-stage-desc">
              {current.desc}
            </p>

            <div className="transformation-specs-table">
              <div className="spec-row">
                <span className="spec-key">CURRICULUM BASE</span>
                <strong className="spec-val">Database Systems Architecture (v2)</strong>
              </div>
              <div className="spec-row">
                <span className="spec-key">VERIFICATION STATE</span>
                <strong className="spec-val">100% Optical Proof Grounded</strong>
              </div>
              <div className="spec-row">
                <span className="spec-key">ACTION REQUIRED</span>
                <strong className="spec-val">
                  {activeStage === 4 ? 'Targeted Walk-through' : activeStage === 5 ? 'Reassessment Unlocked' : 'Interactive Exploration'}
                </strong>
              </div>
            </div>
          </div>

          <div className="transformation-actions-dock">
            <button 
              type="button"
              className="btn-atelier-outline"
              onClick={handleNextPhase}
            >
              <span>Next Phase ({activeStage < 5 ? STAGES[activeStage + 1].id : 'Loop to A'})</span>
              <GlyphArrowRight size={12} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
