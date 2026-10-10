import React from 'react';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';

export default function PrivacyPage() {
  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          <div className="page-header-block">
            <span className="coord-label">DATA PRIVACY & SOVEREIGNTY · GOVERNANCE</span>
            <h1 className="page-title">Privacy Policy</h1>
            <div className="legal-notice-banner">
              <strong>NOTICE: DRAFT VERSION PENDING FINAL LEGAL COUNSEL REVIEW.</strong>
              <span>This policy explains data retention, vector embeddings, and telemetry privacy in VisualAI.</span>
            </div>
          </div>

          <div className="about-prose-content legal-prose">
            <section className="about-section-block">
              <span className="coord-label">01 / DATA COLLECTION PRACTICES</span>
              <h2>Information We Process</h2>
              <p>
                VisualAI processes account credentials (name, email) for session routing and role authorization. 
                When a user ingests curriculum materials, the file is segmented into optical chunks and stored 
                within private storage partitions. Vector embeddings are retained within isolated collections in Qdrant.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">02 / STUDENT ASSESSMENT PRIVACY</span>
              <h2>Diagnostic Telemetry Isolation</h2>
              <p>
                Diagnostic assessment answers and misconception deltas are tied strictly to the student's 
                authorized user ID. Individual misconception data is never broadcast publicly. Aggregated, 
                anonymized analytics are visible only to authorized course educators within the role-protected 
                Educator Hub.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">03 / THIRD-PARTY DISCLOSURE & DATA MONETIZATION</span>
              <h2>Zero Commercial Data Brokerage</h2>
              <p>
                The VisualAI project does not sell, license, or monetize student notes, diagnostic histories, 
                or uploaded textbooks to advertising networks or third-party commercial data brokers.
              </p>
            </section>

            <section className="about-section-block">
              <span className="coord-label">04 / DATA PURGE & DELETION REQUESTS</span>
              <h2>User Control & Erasure</h2>
              <p>
                Users may delete uploaded curriculum sources from their Multimodal Source Library at any time. 
                Upon deletion, source chunks, vector indices, and associated bounding box anchors are purged 
                from runtime memory and vector collections.
              </p>
            </section>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
