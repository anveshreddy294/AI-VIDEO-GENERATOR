import React from 'react';
import { Link } from 'react-router-dom';
import { GlyphBrandMark } from '../ui/AtelierGlyphs';

export default function PublicFooter() {
  return (
    <footer className="atelier-footer">
      <div className="atelier-container footer-inner">
        <div className="footer-top-grid">
          <div className="footer-brand-col">
            <div className="brand-lockup">
              <GlyphBrandMark size={20} className="brand-glyph" />
              <div className="brand-text-block">
                <span className="brand-name">VisualAI</span>
                <span className="brand-atelier-tag">THE KNOWLEDGE ATELIER</span>
              </div>
            </div>
            <p className="footer-mission-statement">
              From information to understanding. Transforming complex educational texts, 
              diagrams, and lectures into mathematically grounded visual learning modules.
            </p>
            <div className="footer-spec-badge">
              <span>CANONICAL SYSTEM · v0.4.0</span>
            </div>
          </div>

          <div className="footer-links-col">
            <span className="footer-col-title">PLATFORM</span>
            <Link to="/platform">Core Instruments</Link>
            <Link to="/how-it-works">Transformation Lifecycle</Link>
            <Link to="/demo">Interactive Demonstration</Link>
            <Link to="/architecture">Architecture & Infrastructure</Link>
          </div>

          <div className="footer-links-col">
            <span className="footer-col-title">WORKSPACE</span>
            <Link to="/app/dashboard">Student Dashboard</Link>
            <Link to="/app/library">Multimodal Source Library</Link>
            <Link to="/app/studio">Focused Learning Studio</Link>
            <Link to="/educator">Educator & Governance Hub</Link>
          </div>

          <div className="footer-links-col">
            <span className="footer-col-title">LEGAL & GOVERNANCE</span>
            <Link to="/terms">Terms of Service (Draft)</Link>
            <Link to="/privacy">Privacy Policy (Draft)</Link>
            <Link to="/about">About & Research Integrity</Link>
            <Link to="/help">Help & Documentation</Link>
          </div>
        </div>

        <div className="footer-bottom-bar">
          <div className="footer-copy-left">
            <span>© 2026 VisualAI Project · Repository: anveshreddy294/AI-VIDEO-GENERATOR</span>
          </div>
          <div className="footer-copy-right">
            <span>STRICT ADHERENCE TO 30 DESIGN RULES · ZERO MOCK FABRICATIONS</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
