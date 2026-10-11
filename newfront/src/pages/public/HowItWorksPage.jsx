import React from 'react';
import { Link } from 'react-router-dom';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';
import TransformationSpecimen from '../../components/ui/TransformationSpecimen';
import { 
  GlyphArrowRight, 
  GlyphCrosshair, 
  GlyphDocument, 
  GlyphEvidence, 
  GlyphDag, 
  GlyphPlay, 
  GlyphCheckmark 
} from '../../components/ui/AtelierGlyphs';

export default function HowItWorksPage() {
  const steps = [
    {
      step: 'PHASE 01 · DOCUMENT INGESTION',
      num: '01',
      title: 'Upload Course Materials & Textbooks',
      plate: '/assets/chapter_source.jpg',
      tag: 'SOURCE INGESTION · TEXTBOOKS & NOTES',
      detail: 'Upload course materials in PDF, DOCX, PNG, or lecture slide formats. VisualAI parses the contents, identifies key concepts, and indexes definitions accurately from your syllabus.',
      input: 'Course Textbook, Slides, or Lecture Notes',
      engine: 'Intelligent Document Analysis',
      output: 'Indexed Course Curriculum'
    },
    {
      step: 'PHASE 02 · CITATION GROUNDING',
      num: '02',
      title: 'Source-Grounded Evidence & Formulas',
      plate: '/assets/chapter_evidence.jpg',
      tag: 'TEXTBOOK CITATIONS · 100% GROUNDED',
      detail: 'Every explanation, rule, and formula is anchored directly to its exact page and section in your source material, guaranteeing reliable information without hallucinations.',
      input: 'Textbook Concepts & Formulas',
      engine: 'Citation & Evidence Verification',
      output: 'Page-Anchored Study Evidence'
    },
    {
      step: 'PHASE 03 · KNOWLEDGE ROADMAP',
      num: '03',
      title: 'Prerequisite Progression Mapping',
      plate: '/assets/chapter_knowledge.jpg',
      tag: 'LEARNING PATHWAY · STEP-BY-STEP',
      detail: 'Concepts are organized into an intuitive prerequisite roadmap, guiding you logically through foundational fundamentals before tackling advanced theorems.',
      input: 'Course Topics & Principles',
      engine: 'Prerequisite Learning Pathway',
      output: 'Structured Study Roadmap'
    },
    {
      step: 'PHASE 04 · INTERACTIVE LESSONS',
      num: '04',
      title: 'Animated Video Lessons & Handwritten Notes',
      plate: '/assets/act4_learning_experience.jpg',
      tag: 'LEARNING STUDIO · HD VIDEO & NOTES',
      detail: 'Explore an intuitive learning workspace featuring clear animated video walkthroughs, authentic handwritten study notes, and concise takeaways tailored to your topic.',
      input: 'Key Concept Explanations',
      engine: 'Visual Lesson & Notes Synthesizer',
      output: 'HD Video Lesson with Study Notes'
    },
    {
      step: 'PHASE 05 · PRACTICE & MASTERY',
      num: '05',
      title: 'Interactive Mock Questions & Progress',
      plate: '/assets/chapter_mastery.jpg',
      tag: 'SELF-ASSESSMENT · TARGETED REVIEW',
      detail: 'Reinforce learning with realistic practice questions. Get immediate friendly feedback and targeted review suggestions whenever a concept needs extra practice.',
      input: 'Student Practice Checkpoints',
      engine: 'Adaptive Mastery Assessment',
      output: 'Clear Understanding & Exam Confidence'
    }
  ];

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          {/* Header Registration */}
          <div className="page-header-block">
            <span className="coord-label">THE ATELIER LIFECYCLE · HOW VISUALAI WORKS</span>
            <h1 className="page-title">From Raw Text to Verified Mastery</h1>
            <p className="page-lead-copy">
              Explore the five continuous phases that transform passive study materials 
              into an active, structured learning experience backed by formal evidence.
            </p>
          </div>

          {/* Workflow Cards Stack */}
          <div className="workflow-steps-stack">
            {steps.map(s => (
              <div key={s.num} className="blueprint-frame workflow-step-card">
                <div className="workflow-step-media">
                  <img src={s.plate} alt={s.title} className="workflow-step-img floating-media-core" />
                  <div className="workflow-step-overlay-tag">
                    <GlyphCrosshair size={11} />
                    <span>{s.tag}</span>
                  </div>
                </div>

                <div className="step-body-col">
                  <div className="step-header-meta">
                    <span className="step-num-badge">{s.step}</span>
                    <span className="coord-label">STAGE 0{s.num} / 05</span>
                  </div>

                  <h2 className="step-title">{s.title}</h2>
                  <p className="step-detail">{s.detail}</p>

                  <div className="step-contract-strip">
                    <div className="step-contract-item">
                      <span className="contract-label">INPUT CONTRACT</span>
                      <strong className="contract-val">{s.input}</strong>
                    </div>
                    <div className="step-contract-item">
                      <span className="contract-label">CORE ENGINE</span>
                      <strong className="contract-val">{s.engine}</strong>
                    </div>
                    <div className="step-contract-item">
                      <span className="contract-label">VERIFIED OUTPUT</span>
                      <strong className="contract-val">{s.output}</strong>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Interactive Live Transformation Specimen */}
          <div className="workflow-transformation-demo-wrapper" style={{ marginTop: '72px' }}>
            <div className="section-header-block">
              <span className="coord-label">EXPERIENCE THE SIX CORE PHASES</span>
              <h2 className="section-title">Interactive Stage Inspection</h2>
              <p className="section-subtext">
                Watch the autonomous progression sequence transform raw textbook scans into targeted remediation.
              </p>
            </div>
            <TransformationSpecimen />
          </div>

          {/* Bottom Actions Row */}
          <div style={{ marginTop: '56px', display: 'flex', gap: '16px', justifyContent: 'center' }}>
            <Link to="/signin" className="btn-atelier-primary">
              <span>Enter Student Workspace</span>
              <GlyphArrowRight size={12} />
            </Link>
            <Link to="/architecture" className="btn-atelier-outline">
              <span>Inspect Infrastructure Architecture</span>
              <GlyphArrowRight size={12} />
            </Link>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
