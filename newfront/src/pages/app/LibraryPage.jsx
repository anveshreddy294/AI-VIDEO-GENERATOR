import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphDocument, 
  GlyphSearch, 
  GlyphArrowRight, 
  GlyphEvidence, 
  GlyphDag, 
  GlyphCheckmark,
  GlyphRotate 
} from '../../components/ui/AtelierGlyphs';

export default function LibraryPage() {
  const { 
    sources, 
    activeSource, 
    setActiveSourceId, 
    uploadSource, 
    isUploading 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const filteredSources = sources.filter(src => {
    const matchesSearch = src.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          src.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          src.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || src.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleUpload = (e) => {
    e.preventDefault();
    if (!selectedFile) return;
    uploadSource(selectedFile);
    setSelectedFile(null);
    setUploadModalOpen(false);
  };

  const handleSelectSource = (src) => {
    setActiveSourceId(src.id);
  };

  return (
    <div className="workspace-page-root">
      {/* Page Header */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">CURRICULUM INGESTION REGISTRY · MULTIMODAL REPOSITORY</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Source Material Library</h1>
            <p className="page-subheading">
              Verified academic textbooks, lecture slides, and experimental lab plates indexed by sub-pixel bounding coordinates.
            </p>
          </div>
          <button 
            type="button" 
            className="btn-atelier-primary"
            onClick={() => setUploadModalOpen(true)}
          >
            <span>+ Ingest Source Material</span>
          </button>
        </div>
      </section>

      {/* Filter and Search Bar */}
      <div className="library-toolbar-strip">
        <div className="search-input-wrapper">
          <GlyphSearch size={14} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by title, subject, or filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="atelier-text-input"
          />
        </div>

        <div className="filter-tabs-group">
          {['ALL', 'READY', 'PROCESSING'].map(status => (
            <button
              key={status}
              type="button"
              className={`filter-tab-pill ${statusFilter === status ? 'active' : ''}`}
              onClick={() => setStatusFilter(status)}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Sources Grid */}
      <div className="library-sources-grid">
        {filteredSources.map(src => {
          const isSelected = activeSource?.id === src.id;
          return (
            <div 
              key={src.id}
              className={`atelier-card source-specimen-card ${isSelected ? 'active-context' : ''}`}
            >
              <div className="card-top-bar">
                <span className="coord-label">{src.subject.toUpperCase()} · VER {src.version}</span>
                <span className={`status-pill ${src.status.toLowerCase()}`}>{src.status}</span>
              </div>

              {/* Contained Media Frame */}
              <div className="specimen-frame-contained">
                <img src={src.coverPlate} alt={src.name} className="source-cover-media" />
                <div className="frame-meta-tag">
                  <span>{src.format} · {src.pages} PAGES · {src.size}</span>
                </div>
              </div>

              <div className="source-card-content">
                <h3 className="source-card-title">{src.name}</h3>
                <p className="source-card-summary">{src.summary}</p>

                <div className="source-provenance-data">
                  <div className="provenance-row">
                    <span className="coord-label">CANONICAL FILE:</span>
                    <span className="mono-file-label">{src.filename}</span>
                  </div>
                  <div className="provenance-row">
                    <span className="coord-label">OPTICAL CONFIDENCE:</span>
                    <span className="provenance-score">{src.opticalConfidence} MATCH</span>
                  </div>
                  <div className="provenance-row">
                    <span className="coord-label">EXTRACTED CONCEPTS:</span>
                    <span>{src.conceptsCount} Invariant Nodes</span>
                  </div>
                </div>

                <div className="source-card-actions">
                  {isSelected ? (
                    <div className="active-badge-indicator">
                      <GlyphCheckmark size={12} />
                      <span>CURRENT ACTIVE CONTEXT</span>
                    </div>
                  ) : (
                    <button 
                      type="button" 
                      className="btn-atelier-outline"
                      onClick={() => handleSelectSource(src)}
                    >
                      <span>Set Active Context</span>
                    </button>
                  )}

                  <button 
                    type="button" 
                    className="btn-atelier-primary"
                    onClick={() => {
                      handleSelectSource(src);
                      navigate('/app/explore');
                    }}
                  >
                    <span>Explore Topics</span>
                    <GlyphDag size={12} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Upload Modal */}
      {uploadModalOpen && (
        <div className="atelier-modal-backdrop">
          <div className="atelier-modal-dialog">
            <div className="modal-header-bar">
              <span className="coord-label">STAGE A · MULTIMODAL INGESTION</span>
              <button 
                type="button" 
                className="modal-close-btn"
                onClick={() => setUploadModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpload} className="modal-form">
              <h2 className="modal-title">Ingest Curriculum Source</h2>
              <p className="modal-description">
                Upload your verified PDF textbook, DOCX lecture transcript, or high-resolution PNG diagram.
                Optical layout parsing and LaTeX formula tokenization will occur in the sandbox.
              </p>

              <div className="file-drop-mount">
                <input 
                  type="file" 
                  accept=".pdf,.docx,.png,.jpg,.jpeg"
                  id="library-file-input"
                  required
                  onChange={(e) => setSelectedFile(e.target.files?.[0])}
                  className="sr-only"
                />
                <label htmlFor="library-file-input" className="drop-mount-label">
                  <GlyphDocument size={28} className="drop-icon" />
                  <strong>{selectedFile ? selectedFile.name : 'Select or drop curriculum file'}</strong>
                  <span className="coord-label">PDF, DOCX, PNG · UP TO 50 MB</span>
                </label>
              </div>

              <div className="modal-actions-strip">
                <button 
                  type="button" 
                  className="btn-atelier-outline"
                  onClick={() => setUploadModalOpen(false)}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={!selectedFile || isUploading}
                  className="btn-atelier-primary"
                >
                  <span>{isUploading ? 'Ingesting...' : 'Confirm Ingestion'}</span>
                  <GlyphArrowRight size={12} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
