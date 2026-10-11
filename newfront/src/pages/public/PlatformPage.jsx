import React from 'react';
import { Link } from 'react-router-dom';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';
import { GlyphArrowRight, GlyphEvidence, GlyphDag, GlyphDocument } from '../../components/ui/AtelierGlyphs';

export default function PlatformPage() {
  const instruments = [
    {
      num: '01',
      title: 'Curriculum & Textbook Ingestion',
      desc: 'Ingests PDF textbooks, lecture slides, and student notes. Extracts key principles, equations, and chapter outlines faithfully from your course material.',
      plate: '/assets/chapter_source.jpg'
    },
    {
      num: '02',
      title: 'Step-by-Step Concept Roadmap',
      desc: 'Organizes complex subject matter into clear prerequisite learning paths. Ensures foundational principles are understood before moving to advanced topics.',
      plate: '/assets/plate_tensor.jpg'
    },
    {
      num: '03',
      title: 'Targeted Practice & Self-Assessment',
      desc: 'Diagnostic practice questions that pinpoint specific misunderstandings, giving immediate friendly explanations to help you master every topic.',
      plate: '/assets/math_geometry_compass.jpg'
    },
    {
      num: '04',
      title: 'Animated Video Lessons & Notes',
      desc: 'Generates intuitive animated video walkthroughs paired with authentic handwritten study notes, transforming abstract ideas into crystal-clear understanding.',
      plate: '/assets/act4_learning_experience.jpg'
    }
  ];

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          <div className="page-header-block">
            <span className="coord-label">PLATFORM INSTRUMENTS · CORE CAPABILITIES</span>
            <h1 className="page-title">The Instruments of Understanding</h1>
            <p className="page-lead-copy">
              VisualAI replaces passive memorization with active structural exploration. 
              Each instrument serves a defined pedagogical purpose.
            </p>
          </div>

          <div className="instruments-stacked-list">
            {instruments.map(inst => (
              <div key={inst.num} className="blueprint-frame instrument-card-row">
                <div className="instrument-media-mount">
                  <img src={inst.plate} alt={inst.title} className="instrument-img floating-media-core" />
                  <span className="instrument-num-tag">{inst.num}</span>
                </div>
                <div className="instrument-text-col">
                  <span className="coord-label">ATELIER INSTRUMENT {inst.num}</span>
                  <h2 className="instrument-title">{inst.title}</h2>
                  <p className="instrument-desc">{inst.desc}</p>
                  <Link to="/app/studio" className="btn-atelier-outline" style={{ marginTop: '16px', display: 'inline-flex' }}>
                    <span>Explore in Workspace</span>
                    <GlyphArrowRight size={12} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
