import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphDag, 
  GlyphEvidence, 
  GlyphArrowRight, 
  GlyphCheckmark,
  GlyphCrosshair,
  GlyphLayers
} from '../../components/ui/AtelierGlyphs';

export default function TopicExplorerPage() {
  const { 
    activeSource, 
    activeConcept, 
    setActiveConceptId, 
    allConcepts, 
    masteryScores 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const conceptsList = Object.values(allConcepts);

  return (
    <div className="workspace-page-root">
      {/* Header */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">CURRICULUM TOPIC ROADMAP · PREREQUISITE STRUCTURE</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Topic Explorer & Concept Roadmap</h1>
            <p className="page-subheading">
              Explore your course topics organized step-by-step with clear prerequisites and textbook page citations.
            </p>
          </div>
          <div className="header-stat-tag">
            <span className="coord-label">ACTIVE GRAPH:</span>
            <strong>{activeSource?.name || 'Database Systems'}</strong>
          </div>
        </div>
      </section>

      {/* Explorer 2-Column Split: Interactive DAG Tree on Left, Evidence Inspector on Right */}
      <div className="explorer-split-grid">
        {/* Left Column: DAG Dependency Graph Canvas */}
        <div className="explorer-dag-pane atelier-card">
          <div className="card-top-bar">
            <div className="title-with-glyph">
              <GlyphDag size={14} />
              <span className="coord-label">DEPENDENCY GRAPH NODES</span>
            </div>
            <span className="card-badge-soft">{conceptsList.length} FORMAL NODES</span>
          </div>

          <div className="dag-nodes-canvas">
            {conceptsList.map((concept, idx) => {
              const isSelected = activeConcept?.id === concept.id;
              const mastery = masteryScores[concept.id] || 0;
              const hasPrereq = concept.prerequisites.length > 0;

              return (
                <div key={concept.id} className="dag-node-wrapper">
                  {hasPrereq && (
                    <div className="dag-connector-line">
                      <div className="connector-arrow">↓</div>
                    </div>
                  )}

                  <div 
                    className={`dag-concept-node ${isSelected ? 'active' : ''}`}
                    onClick={() => setActiveConceptId(concept.id)}
                  >
                    <div className="node-header">
                      <span className="coord-label">NODE 0{idx + 1} · PG {concept.page}</span>
                      <span className={`mastery-pill ${mastery >= 80 ? 'high' : mastery >= 60 ? 'mid' : 'low'}`}>
                        {mastery}% MASTERY
                      </span>
                    </div>

                    <h3 className="node-title">{concept.title}</h3>
                    <p className="node-summary">{concept.summary}</p>

                    <div className="node-footer">
                      <span className="coord-label">
                        {concept.prerequisites.length === 0 ? 'ROOT INVARIANT' : `PREREQUISITE: ${concept.prerequisites.join(', ')}`}
                      </span>
                      <button 
                        type="button" 
                        className="btn-text-select"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveConceptId(concept.id);
                        }}
                      >
                        {isSelected ? 'Selected' : 'Inspect'} →
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Optical Evidence Anchor & Mathematical Formulation */}
        <div className="explorer-inspector-pane">
          {/* Optical Evidence Frame */}
          <div className="atelier-card evidence-specimen-card">
            <div className="card-top-bar">
              <div className="title-with-glyph">
                <GlyphEvidence size={14} />
                <span className="coord-label">OPTICAL PROVENANCE SPECIMEN</span>
              </div>
              <span className="card-badge-soft">PAGE {activeConcept.page}</span>
            </div>

            <div className="evidence-media-mount">
              <img src={activeConcept.plateImage} alt={activeConcept.title} className="evidence-plate-img" />
              
              {/* Architectural Bounding Box Overlay */}
              <div 
                className="bounding-box-overlay"
                style={{
                  top: '18%',
                  left: '12%',
                  width: '74%',
                  height: '42%'
                }}
              >
                <div className="bbox-label-tag">
                  BOUNDING BOX [142, 288, 480, 320] · CONFIDENCE 99.4%
                </div>
              </div>
            </div>

            <div className="evidence-meta-footer">
              <div className="evidence-anchor-spec">
                <GlyphCrosshair size={14} />
                <span>Source: <strong>{activeSource.filename}</strong> (Page {activeConcept.page})</span>
              </div>
            </div>
          </div>

          {/* Mathematical Formalism Card */}
          <div className="atelier-card formalism-card">
            <div className="card-top-bar">
              <span className="coord-label">MATHEMATICAL FORMALISM</span>
              <span className="card-badge-soft">LATEX FORMULATION</span>
            </div>

            <div className="formula-display-box">
              <code className="formal-formula-code">{activeConcept.formula}</code>
            </div>

            <div className="formalism-explanation">
              <h4 className="formalism-heading">{activeConcept.kicker}</h4>
              <p className="formalism-text">{activeConcept.explanation}</p>
            </div>

            <div className="formalism-example-box">
              <span className="coord-label">CONCRETE CURRICULUM EXAMPLE:</span>
              <p className="example-text">{activeConcept.example}</p>
            </div>

            <div className="inspector-actions-strip">
              <button 
                type="button" 
                className="btn-atelier-primary"
                onClick={() => navigate('/app/studio')}
              >
                <span>Launch in Learning Studio</span>
                <GlyphArrowRight size={12} />
              </button>

              <button 
                type="button" 
                className="btn-atelier-outline"
                onClick={() => navigate('/app/assessment')}
              >
                <span>Test Concept Invariant</span>
                <GlyphCheckmark size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
