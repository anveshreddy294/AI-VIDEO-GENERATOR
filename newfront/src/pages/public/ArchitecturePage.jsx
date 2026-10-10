import React from 'react';
import { Link } from 'react-router-dom';
import PublicNavbar from '../../components/navigation/PublicNavbar';
import PublicFooter from '../../components/navigation/PublicFooter';
import { 
  GlyphArrowRight, 
  GlyphDag, 
  GlyphEvidence, 
  GlyphDocument, 
  GlyphPlay, 
  GlyphCheckmark,
  GlyphCrosshair
} from '../../components/ui/AtelierGlyphs';

export default function ArchitecturePage() {
  const components = [
    {
      layer: 'LAYER 01 · CLIENT ATELIER',
      title: 'Frontend Interface System',
      tech: 'React 19 · Vite 6 · Bespoke CSS Tokens · Vanilla Compositor',
      status: 'ACTIVE · RESPONSIVE UI',
      desc: 'Zero-bloat client application built with strict design tokens, accessible keyboard navigation, and responsive multi-pane layout architecture. Strictly eliminates bloated CSS frameworks in favor of deterministic token variables.',
      endpoint: 'CLIENT HOST: http://localhost:5175/',
      latency: '< 16ms RESPONSE TIME',
      contract: 'W3C ARIA 1.2 · 0-4px Hairline Mounts'
    },
    {
      layer: 'LAYER 02 · ORCHESTRATION GATEWAY',
      title: 'FastAPI Microservice Engine',
      tech: 'Python 3.11 · FastAPI · Pydantic V2 · Uvicorn ASGI',
      status: 'STANDBY DAEMON · PORT 8000',
      desc: 'Asynchronous API gateway coordinating ingestion jobs, security legacy boundaries, assessment grading, and pedagogical recommendation lifecycles. Implements deterministic schema validation across all endpoints.',
      endpoint: 'GATEWAY HOST: http://localhost:8000/api/v1',
      latency: '< 45ms P95 LATENCY',
      contract: 'OpenAPI 3.1 · Strict Pydantic Models'
    },
    {
      layer: 'LAYER 03 · STORAGE & IDENTITY',
      title: 'Relational & Authentication Layer',
      tech: 'Supabase PostgreSQL 15 · Row Level Security (RLS)',
      status: 'PERSISTENCE ENGINE',
      desc: 'Maintains user identities, source metadata, learning sessions, and assessment attempt histories with strict cryptographic boundary enforcement. Guarantees referential integrity across concepts and prerequisites.',
      endpoint: 'DATABASE: postgresql://supabase:5432/visualai',
      latency: '< 12ms QUERY DISPATCH',
      contract: 'ACID Relational · Row-Level Security'
    },
    {
      layer: 'LAYER 04 · VECTOR MEMORY',
      title: 'Dense Optical Retrieval Vector Engine',
      tech: 'Qdrant Vector Engine · 1536-dim Dense Embeddings',
      status: 'NEURAL INDEX · PORT 6333',
      desc: 'Stores sub-pixel document chunks, LaTeX equation embeddings, and optical bounding coordinates for deterministic, source-grounded citation retrieval. Pre-filters vector similarity by curriculum document ID.',
      endpoint: 'VECTOR STORE: http://localhost:6333/collections/curriculum',
      latency: '< 28ms ANN SEARCH',
      contract: 'Cosine Distance · Sub-Pixel Bounding Box Payload'
    },
    {
      layer: 'LAYER 05 · PROCEDURAL SYNTHESIS',
      title: 'Visual Animation & Lesson Engine',
      tech: 'Vector Animation Engine · Neural Audio · Whisper Subtitle Alignment',
      status: 'VIDEO SYNTHESIZER',
      desc: 'Synthesizes grounded textbook specifications into intuitive animated lessons. Synchronizes neural narration and subtitle timestamps directly anchored to curriculum concepts.',
      endpoint: 'RENDER WORKER: video_generation_worker.py',
      latency: '2.4s KEYFRAME RENDERING',
      contract: '1080p HD MP4 + Synchronized Subtitles'
    }
  ];

  return (
    <div className="atelier-public-page">
      <PublicNavbar />

      <main className="public-content-main">
        <div className="atelier-container">
          {/* Header Registration */}
          <div className="page-header-block">
            <span className="coord-label">SYSTEM ARCHITECTURE · TECHNICAL SPECIFICATION REF 2026.4</span>
            <h1 className="page-title">Deterministic Engineering Infrastructure</h1>
            <p className="page-lead-copy">
              VisualAI separates inference, vector indexing, session management, and procedural 
              animation into distinct, verifiable services with strict cryptographic boundaries.
            </p>
          </div>

          {/* Interactive Topology Diagram */}
          <div className="arch-topology-diagram">
            <div className="topology-header">
              <div>
                <span className="coord-label">SYSTEM TOPOLOGY OVERVIEW</span>
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', marginTop: '4px' }}>
                  End-to-End Pedagogical Pipeline Architecture
                </h3>
              </div>
              <span className="mount-status-dot">DETERMINISTIC DATA PATH</span>
            </div>

            <div className="topology-flow-row">
              <div className="topology-node-box highlight">
                <span className="node-layer-kicker">LAYER 01</span>
                <div className="node-title">Client Atelier</div>
                <div className="node-tech-tag">React 19 · Vite 6</div>
              </div>

              <div className="topology-node-box">
                <span className="node-layer-kicker">LAYER 02</span>
                <div className="node-title">FastAPI Gateway</div>
                <div className="node-tech-tag">Python 3.11 ASGI</div>
              </div>

              <div className="topology-node-box">
                <span className="node-layer-kicker">LAYER 03</span>
                <div className="node-title">Relational DB</div>
                <div className="node-tech-tag">PostgreSQL RLS</div>
              </div>

              <div className="topology-node-box">
                <span className="node-layer-kicker">LAYER 04</span>
                <div className="node-title">Vector Memory</div>
                <div className="node-tech-tag">Qdrant 1536-dim</div>
              </div>

              <div className="topology-node-box">
                <span className="node-layer-kicker">LAYER 05</span>
                <div className="node-title">Video Synthesizer</div>
                <div className="node-tech-tag">HD Video Engine</div>
              </div>
            </div>
          </div>

          {/* Structured Architectural Layer Cards */}
          <div className="arch-layers-grid">
            {components.map(comp => (
              <div key={comp.layer} className="arch-layer-card">
                <div className="arch-card-top-row">
                  <span className="coord-label">{comp.layer}</span>
                  <span className="mount-status-dot">{comp.status}</span>
                </div>

                <h2 className="arch-layer-title">{comp.title}</h2>
                <div className="arch-tech-badge">{comp.tech}</div>
                <p className="arch-layer-desc">{comp.desc}</p>

                <div className="arch-specs-matrix">
                  <div className="step-contract-item">
                    <span className="contract-label">SYSTEM ENDPOINT</span>
                    <strong className="contract-val" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                      {comp.endpoint}
                    </strong>
                  </div>
                  <div className="step-contract-item">
                    <span className="contract-label">PERFORMANCE BUDGET</span>
                    <strong className="contract-val">{comp.latency}</strong>
                  </div>
                  <div className="step-contract-item">
                    <span className="contract-label">BOUNDARY CONTRACT</span>
                    <strong className="contract-val">{comp.contract}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Actions Row */}
          <div style={{ marginTop: '56px', display: 'flex', gap: '16px', justifyContent: 'center' }}>
            <Link to="/signin" className="btn-atelier-primary">
              <span>Enter Workspace</span>
              <GlyphArrowRight size={12} />
            </Link>
            <Link to="/how-it-works" className="btn-atelier-outline">
              <span>Inspect Workflow Pipeline</span>
              <GlyphArrowRight size={12} />
            </Link>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
