import React from 'react';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';

export default function TermsPage() {
  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          <div className="page-header-block">
            <span className="coord-label">LEGAL SPECIFICATION · GOVERNANCE</span>
            <h1 className="page-title">Terms of Service</h1>
            <div className="legal-notice-banner">
              <strong>NOTICE: DRAFT VERSION PENDING FINAL LEGAL COUNSEL REVIEW.</strong>
              <span>This document outlines platform usage rights and intellectual property terms for VisualAI.</span>
            </div>
          </div>

          <div className="about-prose-content legal-prose">
            <section className="about-section-block">
              <span className="coord-label">01 / ACCEPTANCE OF TERMS</span>
              <h2>Usage Agreement</h2>
              <p>
                By accessing the VisualAI platform, including public demonstrations and authenticated 
                workspaces, users agree to abide by these terms. This product is deployed as an educational 
                research and visual learning tool under active academic and technical development.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">02 / USER-PROVIDED CURRICULUM MATERIALS</span>
              <h2>Intellectual Property & Ownership</h2>
              <p>
                Users retain full intellectual property rights to the textbooks, slide decks, lab notes, 
                and manuscripts they upload. VisualAI processes uploaded materials solely for OCR 
                extraction, mathematical vector indexing, and personalized learning session delivery. 
                Materials are not resold, distributed publicly, or utilized for ungrounded third-party training.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">03 / ACADEMIC INTEGRITY & GENERATED CONTENT</span>
              <h2>Responsible Educational Use</h2>
              <p>
                VisualAI is designed to enhance conceptual understanding. Users agree not to utilize 
                automated assessment solutions or procedural derivations in violation of their academic 
                institution's honor codes or testing policies.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">04 / SERVICE LIMITATIONS & DISCLAIMERS</span>
              <h2>Experimental Technology Notice</h2>
              <p>
                While the system enforces deterministic optical grounding, machine learning extraction 
                and automated Manim compilation are provided on an "as-is" basis. The VisualAI project 
                disclaims liability for typographical misinterpretations arising from low-resolution scans.
              </p>
            </section>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
