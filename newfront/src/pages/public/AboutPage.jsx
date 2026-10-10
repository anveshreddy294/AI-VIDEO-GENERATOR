import React from 'react';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';

export default function AboutPage() {
  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          <div className="page-header-block">
            <span className="coord-label">MISSION & PRINCIPLES · ABOUT VISUALAI</span>
            <h1 className="page-title">The Purpose of the Knowledge Atelier</h1>
            <p className="page-lede">
              We believe students do not need another generic chatbot generating polite summaries. 
              They need structural perspective, visual derivations, and rigorous evidence grounding.
            </p>
          </div>

          <div className="about-prose-content">
            <section className="about-section-block">
              <span className="coord-label">01 / CORE MISSION</span>
              <h2>Transforming Information into Understanding</h2>
              <p>
                Dense academic textbooks and lectures often hide simple, elegant invariants behind 
                walls of ungrounded notation. VisualAI isolates the exact conceptual bottleneck 
                and builds a personalized visual proof directly grounded in the student's study notes.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">02 / RESPONSIBLE AI PRINCIPLES</span>
              <h2>Deterministic Grounding & Zero Hallucination Policy</h2>
              <p>
                VisualAI never invents facts, citations, or formulas. If an ingested source does not 
                contain sufficient evidence to answer an inquiry, the system explicitly reports retrieval 
                insufficiency rather than generating speculative filler.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">03 / PRODUCT BOUNDARIES & LIMITATIONS</span>
              <h2>Truthful Operational Capabilities</h2>
              <p>
                Optical OCR coordinate extraction requires clean, high-resolution scans. Highly cursive 
                handwritten annotations may fail validation. In such cases, the system reports 
                verification failure and recommends uploading a text-based PDF or cleaner scan.
              </p>
            </section>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
