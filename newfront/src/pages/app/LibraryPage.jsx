import React, { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { toUserMessage } from '../../services/api/errors';
import { humanJobStage, humanSourceStatus } from '../../services/api/adapters';
import { GlyphArrowRight, GlyphCheckmark, GlyphDocument, GlyphSearch, GlyphRotate } from '../../components/ui/AtelierGlyphs';
import { WorkflowStepper } from '../../components/ui/WorkflowStepper';
import { UPLOAD_WORKFLOW_STEPS, uploadWorkflowState } from '../../services/workflowState';
import { LoadingContent } from '../../components/ui/Skeleton';

export default function LibraryPage() {
  const { 
    sources, 
    activeSource, 
    setActiveSourceId, 
    uploadSource, 
    retryUpload, 
    isUploading, 
    uploadJob, 
    uploadError, workspaceStatus, workspaceError
  } = useAtelierWorkspace();

  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [file, setFile] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const jobSourceId = uploadJob?.result?.source_id || uploadJob?.metadata?.source_id;
  const jobSource = sources.find(source => source.id === jobSourceId);

  const filtered = useMemo(() => sources.filter(source => {
    const text = `${source.name} ${source.filename} ${source.format}`.toLowerCase();
    const statusMatches = filter === 'ALL' || 
      (filter === 'READY' && source.contentReady) || source.status === filter ||
      (filter === 'PROCESSING' && ['INDEXING', 'EXTRACTING', 'PROCESSING'].includes(source.status));
    return text.includes(query.toLowerCase()) && statusMatches;
  }), [sources, query, filter]);

  const counts = useMemo(() => {
    return {
      ALL: sources.length,
      READY: sources.filter(s => s.contentReady || s.status === 'READY').length,
      PROCESSING: sources.filter(s => ['INDEXING', 'EXTRACTING', 'PROCESSING'].includes(s.status)).length,
      FAILED: sources.filter(s => s.status === 'FAILED').length
    };
  }, [sources]);

  const submit = async event => {
    if (event) event.preventDefault();
    if (!file) return;
    try { 
      await uploadSource(file); 
      setFile(null); 
    } catch { 
      /* error is rendered from workspace context */ 
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  return (
    <div className="workspace-page-root">
      {/* Architectural Header */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="coord-label">MY MATERIALS · YOUR UPLOADED SOURCES</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">My Materials</h1>
            <p className="page-subheading">
              Upload a PDF, image or supported study note. We will read it first, then prepare it for learning.
            </p>
          </div>
          <form onSubmit={submit} className="material-upload-actions">
            <button type="button" className="btn-atelier-outline" onClick={() => fileInput.current?.click()} disabled={isUploading}>
              <GlyphDocument size={12} /> {file ? file.name : 'Choose file'}
            </button>
              <input 
                ref={fileInput}
                aria-label="Choose study material"
                type="file" 
                hidden 
                accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.mp4,.mov,.mkv" 
                onChange={event => setFile(event.target.files?.[0])} 
              />
            <button 
              type="submit" 
              className="btn-atelier-primary" 
              disabled={!file || isUploading}
            >
              {isUploading ? 'Reading material…' : 'Upload Material'} <GlyphArrowRight size={12} />
            </button>
          </form>
        </div>

        {uploadJob && (
          <div className="materials-workflow">
            <WorkflowStepper steps={UPLOAD_WORKFLOW_STEPS} {...uploadWorkflowState(uploadJob, jobSource, uploadError)} label="Material processing" />
          </div>
        )}

        {uploadError && (
          <div className="signin-disclaimer-box" role="alert" style={{ marginTop: '12px' }}>
            <p>
              {toUserMessage(uploadError)}
                {uploadJob?.job_id && uploadJob?.retry_supported !== false && (
                  <button type="button" className="btn-atelier-outline" onClick={() => retryUpload().catch(() => {})} style={{ marginLeft: '10px' }}>
                  <GlyphRotate size={11} /> Try again
                </button>
              )}
            </p>
          </div>
        )}
      </section>

      {/* Tactile Architectural Dropzone Stage */}
      <section 
        role="button"
        tabIndex={isUploading ? -1 : 0}
        aria-label="Choose or drop study material"
        aria-disabled={isUploading}
        className={`blueprint-frame atelier-dropzone ${isDragOver ? 'drag-active' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{ marginBottom: '24px', cursor: 'pointer' }}
        onClick={() => { if (!isUploading) fileInput.current?.click(); }}
        onKeyDown={event => { if (!isUploading && ['Enter', ' '].includes(event.key)) { event.preventDefault(); fileInput.current?.click(); } }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--terracotta)' }}>
          <GlyphDocument size={22} />
          <span className="coord-label" style={{ color: 'var(--terracotta)', fontWeight: 600, fontSize: '14px' }}>
            Add study material
          </span>
        </div>
        <p style={{ margin: '10px 0 6px', fontSize: '17px', color: 'var(--ink-primary)', fontWeight: 500 }}>
          {file ? `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'Drag and drop course material here, or click to browse'}
        </p>
        <span style={{ fontSize: '15px', color: 'var(--ink-muted)', lineHeight: 1.6 }}>
          We will read your file and save the available content to your workspace.
        </span>
        <div className="format-badges-row" style={{ marginTop: '14px', gap: '10px' }}>
          <span className="format-pill">PDF</span><span className="format-pill">PNG / JPG / WEBP</span>
          <span className="format-pill">TXT</span><span className="format-pill">MP4 / MOV / MKV</span><span className="format-pill">Up to 200 MB</span>
        </div>
      </section>

      {/* Library Toolbar Strip */}
      <div className="library-toolbar-strip" style={{ marginBottom: '16px' }}>
        <div className="search-input-wrapper">
          <GlyphSearch size={16} className="search-icon" />
          <input 
            className="atelier-text-input" 
            aria-label="Search your materials"
            placeholder="Search your materials…" 
            value={query} 
            onChange={event => setQuery(event.target.value)} 
            style={{ fontSize: '16.5px' }}
          />
        </div>
        <div className="filter-tabs-group">
          {[
            { id: 'ALL', label: 'ALL', count: counts.ALL },
            { id: 'READY', label: 'READY TO LEARN', count: counts.READY },
            { id: 'PROCESSING', label: 'IN PROGRESS', count: counts.PROCESSING },
            { id: 'FAILED', label: 'NEEDS ATTENTION', count: counts.FAILED }
          ].map(tab => (
            <button 
              key={tab.id} 
              type="button" 
              className={`filter-tab-pill ${filter === tab.id ? 'active' : ''}`} 
              aria-pressed={filter === tab.id}
              onClick={() => setFilter(tab.id)}
              style={{ fontSize: '13.5px', padding: '6px 14px' }}
            >
              {tab.label} <span style={{ opacity: 0.7, fontSize: '12px' }}>({tab.count})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Library Sources Vertical Downward Flow — Unboxed Matter, Zero Images */}
      <div className="library-sources-grid">
        {workspaceError && <p role="alert">{toUserMessage(workspaceError)}</p>}
        {workspaceStatus === 'loading' ? <LoadingContent label="Loading materials…" lines={5} /> : filtered.length === 0 ? (
          <div style={{ padding: '28px 0', borderBottom: '1px solid var(--border)' }}>
            <p className="coord-label">No matching materials are available.</p>
          </div>
        ) : (
          filtered.map(source => {
            const selected = source.id === activeSource?.id;
            const conceptDisplay = source.conceptsCount !== null && source.conceptsCount !== undefined
              ? `${source.conceptsCount} Concepts`
              : (source.contentReady ? 'Content available' : 'Not available yet');

            return (
              <article 
                key={source.id} 
                className={`source-specimen-card ${selected ? 'active-context' : ''}`}
              >
                <div className="card-top-bar" style={{ marginBottom: '8px' }}>
                  <span className="coord-label">{source.format} · VERSION {source.version}</span>
                  <span className={`status-pill ${String(source.status).toLowerCase()}`}>
                    {humanSourceStatus(source.status)}
                  </span>
                </div>

                <div className="source-card-content">
                  <h3 className="source-card-title">{source.name}</h3>
                  <p className="source-card-summary">
                    {source.summary} · Source file: <span className="mono">{source.filename}</span>
                  </p>

                  <WorkflowStepper steps={UPLOAD_WORKFLOW_STEPS} {...uploadWorkflowState(null, source)} label={`Processing for ${source.name}`} />
                  <details className="source-details"><summary>Material details</summary><p>{conceptDisplay} · Version {source.version}</p><p className="mono">Source: {source.id}</p></details>

                  {/* Actions Row: Select Material, Create Source Lesson */}
                  <div className="source-card-actions">
                    {selected ? (
                      <div className="active-badge-indicator">
                        <GlyphCheckmark size={14} />
                        <span>CURRENT MATERIAL SELECTED</span>
                      </div>
                    ) : (
                      <button 
                        type="button" 
                        className="btn-atelier-outline" 
                        onClick={() => setActiveSourceId(source.id)}
                      >
                        Select Material
                      </button>
                    )}

                    {source.contentReady && (
                      <button 
                        type="button" 
                        className="btn-atelier-primary" 
                        onClick={() => { 
                          setActiveSourceId(source.id); 
                          navigate('/app/explore?mode=source'); 
                        }}
                      >
                        Create Source Lesson <GlyphArrowRight size={13} />
                      </button>
                    )}
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
