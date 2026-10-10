import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';
import TransformationSpecimen from '../../components/ui/TransformationSpecimen';
import { 
  GlyphArrowRight, 
  GlyphArrowUpRight, 
  GlyphDocument, 
  GlyphEvidence, 
  GlyphDag, 
  GlyphCheckmark,
  GlyphCrosshair,
  GlyphPlay
} from '../../components/ui/AtelierGlyphs';

export default function LandingPage() {
  const heroRef = useRef(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e) => {
    if (!heroRef.current) return;
    const rect = heroRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    setMousePos({ 
      x: Math.max(-1, Math.min(1, x)), 
      y: Math.max(-1, Math.min(1, y)) 
    });
  };

  const handleMouseLeave = () => {
    setMousePos({ x: 0, y: 0 });
  };

  const specimens = [
    {
      code: 'TOPIC 01 · ASTROPHYSICS',
      title: 'Two-Body Gravitational Potentials',
      formula: 'F = G (m_1 m_2) / r^2',
      plate: '/assets/astronomy_telescope_galaxy.jpg',
      tag: 'Orbital Speed & Gravity'
    },
    {
      code: 'TOPIC 02 · PHYSICS & CALCULUS',
      title: 'Wave Functions & Harmonic Motion',
      formula: 'f(t) = a_0/2 + ∑ [a_n cos(nωt)]',
      plate: '/assets/physics_blackboard.jpg',
      tag: 'Harmonic Derivations'
    },
    {
      code: 'TOPIC 03 · CELLULAR BIOLOGY',
      title: 'Double-Helix DNA Base Pairing',
      formula: 'A-T, G-C Hydrogen Bond Dynamics',
      plate: '/assets/biology_cell_microscope.jpg',
      tag: 'Transcription Factors'
    },
    {
      code: 'TOPIC 04 · COMPUTER SCIENCE',
      title: 'Relational Database Queries & Indexing',
      formula: 'B+ Tree Clustered Index Traversal',
      plate: '/assets/database_code_screen.jpg',
      tag: 'Primary Key Indexing'
    }
  ];

  const streamItems = [
    {
      plate: '/assets/study_desk_mac.jpg',
      code: 'STUDIO 01 · STUDY SETUP',
      title: 'Interactive Study Workspace',
      formula: 'Active Lecture Note Ingestion'
    },
    {
      plate: '/assets/notebook_handwritten.jpg',
      code: 'NOTES 02 · STUDENT NOTES',
      title: 'Handwritten Key Takeaways',
      formula: 'Summary Checkpoints & Rules'
    },
    {
      plate: '/assets/library_books_hall.jpg',
      code: 'ARCHIVE 03 · TEXTBOOK REPOSITORY',
      title: 'Course Literature Archive',
      formula: 'Full Library Ingestion'
    },
    {
      plate: '/assets/student_studying.jpg',
      code: 'SESSION 04 · ACTIVE PRACTICE',
      title: 'Focused Concept Checkpoints',
      formula: 'Mock Questions & Self-Tests'
    },
    {
      plate: '/assets/physics_blackboard.jpg',
      code: 'DERIVATION 05 · APPLIED PHYSICS',
      title: 'Classroom Formula Proofs',
      formula: 'Step-by-Step Derivations'
    },
    {
      plate: '/assets/astronomy_telescope_galaxy.jpg',
      code: 'COSMOLOGY 06 · ASTROPHYSICS',
      title: 'Planetary Mechanics & Orbits',
      formula: 'Gravitational Field Calculations'
    }
  ];

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main>
        {/* 1. HERO VIEWPORT WITH INTERACTIVE FLOATING CONSTELLATION */}
        <section 
          ref={heroRef}
          className="atelier-hero-section"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            '--mx': mousePos.x,
            '--my': mousePos.y
          }}
        >

          <div className="atelier-container" style={{ position: 'relative', zIndex: 2 }}>
            {/* Top Registration Index */}
            <div className="hero-registration-line">
              <span className="coord-label">LAT 37.7749° N · SYSTEM DESIGN SPECIFICATION · REF 2026.4</span>
              <span className="coord-label">ARCHITECTURAL EDITION · THE KNOWLEDGE ATELIER</span>
            </div>

            <div className="hero-grid-layout">
              {/* Left Column: Proposition */}
              <div className="hero-proposition-column">
                <span className="hero-kicker-tag">THE INTELLIGENT LEARNING INSTRUMENT</span>
                
                <h1 className="hero-editorial-headline">
                  From information<br />
                  <span className="headline-italic">to understanding.</span>
                </h1>

                <p className="hero-lead-text">
                  Turn dense textbooks, technical notes, and problem sets into 
                  optically verified evidence, topological concept graphs, and 
                  adaptive video lessons.
                </p>

                <div className="hero-actions-group">
                  <Link to="/signin" className="btn-atelier-primary hero-btn">
                    <span>Enter Student Workspace</span>
                    <GlyphArrowRight size={13} />
                  </Link>
                  <Link to="/demo" className="btn-atelier-outline hero-btn">
                    <span>Inspect Interactive Demo</span>
                    <GlyphArrowUpRight size={13} />
                  </Link>
                </div>

                <div className="hero-provenance-strip">
                  <div className="prov-cell">
                    <span className="prov-k">STUDY FOUNDATION</span>
                    <strong className="prov-v">Textbook-Grounded Concepts</strong>
                  </div>
                  <div className="prov-cell">
                    <span className="prov-k">VISUAL LESSONS</span>
                    <strong className="prov-v">Animated Explanations</strong>
                  </div>
                  <div className="prov-cell">
                    <span className="prov-k">PRACTICE & MASTERY</span>
                    <strong className="prov-v">Targeted Self-Assessment</strong>
                  </div>
                </div>
              </div>

              {/* Right Column: Multi-Layer Floating Architectural Constellation */}
              <div className="hero-visual-column">
                {/* Floating Precision Micro-Chips */}
                <div className="hero-floating-chip chip-top-left">
                  <GlyphEvidence size={12} />
                  <span>OCR REGISTRATION [142, 288]</span>
                </div>

                <div className="hero-floating-chip chip-mid-left">
                  <GlyphPlay size={11} />
                  <span>INTERACTIVE LESSON STAGE</span>
                </div>

                {/* Satellite Floating Plate 1: Celestial Orbit (Top-Right Levitating) */}
                <div className="satellite-floating-plate sat-plate-orbit">
                  <div className="sat-plate-header">
                    <span className="coord-label">PHYSICS · CELESTIAL MECHANICS</span>
                    <GlyphCrosshair size={10} />
                  </div>
                  <div className="sat-plate-media">
                    <img 
                      src="/assets/astronomy_telescope_galaxy.jpg" 
                      alt="Planetary Mechanics and Orbits" 
                      className="sat-plate-img floating-media-core" 
                    />
                  </div>
                  <div className="sat-plate-caption">
                    F = G (m₁ m₂) / r²
                  </div>
                </div>

                {/* Central Main Floating Knowledge Stage */}
                <div className="hero-mount-card floating-hero-plate">
                  <div className="mount-meta-header">
                    <span className="coord-label">FIG 01 · OPTICAL KNOWLEDGE STAGE</span>
                    <span className="mount-status-dot">ACTIVE ENGINE</span>
                  </div>

                  <div className="mount-contained-media">
                    <img 
                      src="/assets/hero_celestial_botanical.jpg" 
                      alt="The Knowledge Atelier Botanical & Celestial Stage" 
                      className="mount-hero-img floating-media-core" 
                    />
                    <div className="mount-overlay-badge">
                      <GlyphCrosshair size={13} />
                      <span>VERIFIED CURRICULUM · OPTICALLY GROUNDED</span>
                    </div>
                  </div>

                  <div className="mount-caption-bar">
                    <span className="mount-caption-title">Database Systems (Chapter 3) · Entity Integrity</span>
                    <Link to="/app/studio" className="mount-link-action">
                      <span>Watch Lesson</span>
                      <GlyphArrowRight size={11} />
                    </Link>
                  </div>
                </div>

                {/* Satellite Floating Plate 2: Analog Laboratory Notebook (Bottom-Left Levitating) */}
                <div className="satellite-floating-plate sat-plate-notebook">
                  <div className="sat-plate-header">
                    <span className="coord-label">STUDY NOTES · LAB NOTEBOOK</span>
                    <GlyphDocument size={10} />
                  </div>
                  <div className="sat-plate-media">
                    <img 
                      src="/assets/notebook_handwritten.jpg" 
                      alt="Student Study Notebook" 
                      className="sat-plate-img floating-media-core" 
                    />
                  </div>
                  <div className="sat-plate-caption">
                    H(s) = [K ω_n²] / [s² + 2ζω_n s + ω_n²]
                  </div>
                </div>

                {/* Bottom-Right Floating Invariant Tag */}
                <div className="hero-floating-chip chip-bottom-right">
                  <GlyphCheckmark size={12} />
                  <span>RULE: Every row must have a unique identifier</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2. SIGNATURE TRANSFORMATION SECTION */}
        <section className="section-signature-transformation">
          <div className="atelier-container">
            <div className="section-header-block">
              <span className="coord-label">01 / THE CORE PEDAGOGICAL INSTRUMENT</span>
              <h2 className="section-title">The Complete Knowledge Transformation</h2>
              <p className="section-subtext">
                Every learning journey follows six verified states: from raw textbook scan to targeted cognitive improvement.
              </p>
            </div>

            {/* Interactive 6-Stage Transformation Specimen with Floating Stage Plate */}
            <TransformationSpecimen />
          </div>
        </section>

        {/* 2.5 CONTINUOUS FLOATING ARCHIVE STREAM */}
        <section className="section-floating-stream">
          <div className="atelier-container">
            <div className="stream-header-strip">
              <div className="stream-header-left">
                <span className="coord-label">02 / CONTINUOUS EXTRACTION STREAM</span>
                <h2 className="stream-title">Autonomous Curriculum Specimen Corridor</h2>
                <p className="stream-subtext">
                  Continuous optical extraction across mathematics, astrophysics, analog systems, and biology.
                </p>
              </div>
              <span className="coord-label">AUTONOMOUS GLIDE · 6 CONCURRENT PLATES</span>
            </div>
          </div>

          <div className="floating-stream-viewport">
            <div className="floating-stream-track">
              {[...streamItems, ...streamItems].map((item, idx) => (
                <div 
                  key={`${item.code}-${idx}`} 
                  className={`floating-stream-card stream-card-alt-${(idx % 3) + 1}`}
                >
                  <div className="stream-card-media">
                    <img src={item.plate} alt={item.title} className="stream-card-img floating-media-core" />
                    <div className="stream-card-overlay-tag">{item.code}</div>
                  </div>
                  <div className="stream-card-body">
                    <div className="stream-card-title">{item.title}</div>
                    <code className="stream-card-formula">{item.formula}</code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 3. MULTIDISCIPLINARY SPECIMEN GALLERY WITH UNDULATING FLOATING CARDS */}
        <section className="section-specimen-gallery">
          <div className="atelier-container">
            <div className="section-header-block">
              <span className="coord-label">03 / MULTIMODAL CURRICULUM ARCHIVE</span>
              <h2 className="section-title">Rigorous Cross-Disciplinary Specimens</h2>
              <p className="section-subtext">
                Inspect how VisualAI extracts formal definitions and visual derivations across STEM curricula.
              </p>
            </div>

            <div className="specimens-grid">
              {specimens.map((item, idx) => (
                <div 
                  key={item.code} 
                  className={`specimen-card-unit floating-specimen-card float-wave-${idx + 1}`}
                >
                  <div className="specimen-card-media-mount">
                    <img 
                      src={item.plate} 
                      alt={item.title} 
                      className="specimen-card-img floating-media-core" 
                    />
                    <div className="specimen-card-tag">{item.tag}</div>
                  </div>
                  <div className="specimen-card-body">
                    <span className="coord-label">{item.code}</span>
                    <h3 className="specimen-card-title">{item.title}</h3>
                    <code className="specimen-card-formula">{item.formula}</code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 4. ARCHITECTURAL CALL TO ACTION WITH FLOATING REPOSITORY PLATE */}
        <section className="section-atelier-cta">
          <div className="atelier-container">
            <div className="cta-contained-panel">
              <div className="cta-content-column">
                <span className="coord-label">04 / START RESEARCH & STUDY</span>
                <h2 className="cta-headline">Bring your most difficult chapter.</h2>
                <p className="cta-description">
                  Upload raw lecture slides, handwritten lab notes, or PDF textbooks. 
                  Experience procedural visual proofs built specifically for your conceptual hurdles.
                </p>
                <div className="cta-actions-row">
                  <Link to="/signin" className="btn-atelier-primary">
                    <span>Enter Student Studio</span>
                    <GlyphArrowRight size={12} />
                  </Link>
                  <Link to="/how-it-works" className="btn-atelier-outline">
                    <span>Read Technical Workflow</span>
                  </Link>
                </div>
              </div>

              {/* Floating Architectural Proof Plate */}
              <div className="cta-floating-preview-card">
                <div className="cta-preview-media">
                  <img 
                    src="/assets/library_books_hall.jpg" 
                    alt="University Library Source Archive" 
                    className="cta-preview-img floating-media-core" 
                  />
                </div>
                <div className="cta-preview-footer">
                  <span className="coord-label">CURRICULUM ARCHIVE · VERIFIED SOURCES</span>
                  <span style={{ color: 'var(--terracotta)', fontWeight: 600 }}>READY TO LEARN</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
