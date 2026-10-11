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
            <span className="coord-label">EXPLORE VISUALAI</span>
            <h1 className="demo-title">Interactive Product Demonstration</h1>
            <p className="demo-subtitle">
              Explore illustrated examples of a learning workspace. Sign in to create lessons and see your own results.
            </p>
          </div>

          <div className="demo-tabs-bar">
            <button 
              className={`demo-tab-btn ${activeTab === 'transformation' ? 'active' : ''}`}
              onClick={() => setActiveTab('transformation')}
            >
               Learning guide
            </button>
            <button 
              className={`demo-tab-btn ${activeTab === 'ask' ? 'active' : ''}`}
              onClick={() => setActiveTab('ask')}
            >
               Example question
            </button>
            <button 
              className={`demo-tab-btn ${activeTab === 'video' ? 'active' : ''}`}
              onClick={() => setActiveTab('video')}
            >
               Video guide
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
                    <span className="coord-label">ILLUSTRATIVE ANSWER</span>
                    <p className="ask-answer-text">
                      According to <em>Database Systems Architecture (v2 · § 3.2)</em>: 
                      "Entity Integrity dictates that primary key attributes identify distinct entities 
                      and therefore must be unconditionally unique and non-null."
                    </p>
                    <div className="ask-citation-pill">
                      <GlyphCrosshair size={12} />
                       <span>Example citation format: chapter, page and source passage</span>
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
                    <span className="video-demo-tag">VIDEO LESSON ILLUSTRATION</span>
                    <span className="video-demo-status">Generate and play your video in the workspace</span>
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
