import React, { useState } from 'react';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';

export default function HelpPage() {
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    {
      q: 'What file formats can I bring into the Knowledge Atelier?',
      a: 'VisualAI supports standard PDF textbooks, DOCX lecture outlines, high-resolution PNG/JPG schematics and notes, and supported educational video files (up to 25 MB).'
    },
    {
      q: 'How does VisualAI ensure answers are not fabricated?',
      a: 'Every answer is strictly synthesized from vector chunks retrieved from your uploaded document. Clickable citation badges link directly to the page and bounding box region.'
    },
    {
      q: 'Can instructors deploy VisualAI for their university classrooms?',
      a: 'Yes. The platform includes a dedicated, role-protected Educator Hub that aggregates student concept-level mastery and flags common misconception patterns across cohorts.'
    },
    {
      q: 'What is the role of the Video Lesson Studio?',
      a: 'The Video Lesson Studio turns complex syllabus topics, theorems, and equations into clear, animated video walkthroughs paired with authentic student study notes so you can understand difficult ideas faster.'
    }
  ];

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          <div className="page-header-block">
            <span className="coord-label">GUIDANCE & DOCUMENTATION · HELP CENTER</span>
            <h1 className="page-title">Frequently Asked Questions & Support</h1>
            <p className="page-lede">
              Practical answers regarding source ingestion, optical verification, 
              and student assessment mechanics.
            </p>
          </div>

          <div className="help-faqs-accordion">
            {faqs.map((faq, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div key={idx} className={`faq-accordion-item ${isOpen ? 'open' : ''}`}>
                  <button 
                    type="button" 
                    className="faq-question-btn"
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    aria-expanded={isOpen}
                  >
                    <span className="faq-q-text">{faq.q}</span>
                    <span className="faq-toggle-sym">{isOpen ? '−' : '+'}</span>
                  </button>
                  {isOpen && (
                    <div className="faq-answer-pane">
                      <p>{faq.a}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
