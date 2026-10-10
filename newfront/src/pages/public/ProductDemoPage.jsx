import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';
import TransformationSpecimen from '../../components/ui/TransformationSpecimen';
import { 
  GlyphArrowRight, 
  GlyphDocument, 
  GlyphEvidence, 
  GlyphDag, 
  GlyphPlay, 
  GlyphCheckmark,
  GlyphCrosshair
} from '../../components/ui/AtelierGlyphs';

export default function ProductDemoPage() {
  const [activeTab, setActiveTab] = useState('transformation');

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="demo-page-main">
        <div className="atelier-container">
          <div className="demo-header-strip">
            <span className="coord-label">INTERACTIVE VERIFICATION SUITE · FIXTURE CONTRACT V1</span>
            <h1 className="demo-title">Interactive Product Demonstration</h1>
            <p className="demo-subtitle">
              Inspect the end-to-end pedagogical pipeline backed by canonical curriculum contracts. 
              No fake interfaces or mock fabrications.
            </p>
          </div>

          <div className="demo-tabs-bar">
            <button 
              className={`demo-tab-btn ${activeTab === 'transformation' ? 'active' : ''}`}
              onClick={() => setActiveTab('transformation')}
            >
              01 · Six-Stage Transformation
            </button>
            <button 
              className={`demo-tab-btn ${activeTab === 'ask' ? 'active' : ''}`}
              onClick={() => setActiveTab('ask')}
            >
              02 · Source-Grounded ASK Demo
            </button>
            <button 
              className={`demo-tab-btn ${activeTab === 'video' ? 'active' : ''}`}
              onClick={() => setActiveTab('video')}
            >
              03 · Visual Lesson Studio
            </button>
          </div>

          <div className="demo-content-body">
            {activeTab === 'transformation' && (
              <div className="demo-panel">
                <TransformationSpecimen />
              </div>
            )}

            {activeTab === 'ask' && (
              <div className="demo-panel ask-demo-panel">
                <div className="ask-specimen-grid">
                  <div className="ask-input-col">
                    <span className="coord-label">QUESTION PROBE</span>
                    <h3 className="ask-demo-query">
                      "Why does a primary key strictly disallow null values under the Entity Integrity rule?"
                    </h3>
                    <div className="ask-grounding-spec">
                      <span>BOUND TO: Database_Systems_v2_Chapter3.pdf</span>
                      <span>PAGE 7 · PARAGRAPH 3.2</span>
                    </div>
                  </div>
                  <div className="ask-response-col">
                    <span className="coord-label">GROUNDED CITATION OUTPUT</span>
                    <p className="ask-answer-text">
                      According to <em>Database Systems Architecture (v2 · § 3.2)</em>: 
                      "Entity Integrity dictates that primary key attributes identify distinct entities 
                      and therefore must be unconditionally unique and non-null."
                    </p>
                    <div className="ask-citation-pill">
                      <GlyphCrosshair size={12} />
                      <span>Verified Citation: Page 7 · Bounding Box [142, 288, 480, 320]</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'video' && (
              <div className="demo-panel video-demo-panel">
                <div className="video-demo-viewport-box">
                  <img src="/assets/database_code_screen.jpg" alt="Video frame" className="video-demo-img" />
                  <div className="video-demo-overlay">
                    <span className="video-demo-tag">LESSON DEMO · HD 1080P</span>
                    <span className="video-demo-status">INTERACTIVE VIDEO PLAYER READY</span>
                  </div>
                </div>
                <div className="video-demo-caption">
                  <p>
                    <strong>Clear Visual Lesson Walkthrough:</strong> Engaging animated lesson 
                    derived directly from your syllabus topics, showing step-by-step solutions and key principles.
                  </p>
                  <Link to="/app/video" className="btn-atelier-primary" style={{ marginTop: '14px' }}>
                    <span>Open Video Studio in Workspace</span>
                    <GlyphArrowRight size={12} />
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
