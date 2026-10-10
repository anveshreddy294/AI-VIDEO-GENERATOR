import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphPlay, 
  GlyphPause, 
  GlyphArrowRight, 
  GlyphCheckmark,
  GlyphRotate,
  GlyphDocument
} from '../../components/ui/AtelierGlyphs';

export default function VideoStudioPage() {
  const { videoStoryboard, showNotification } = useAtelierWorkspace();
  const navigate = useNavigate();
  const [activeSceneIdx, setActiveSceneIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [promptTopic, setPromptTopic] = useState('Entity Integrity & Primary Keys');
  const [currentProgress, setCurrentProgress] = useState(25);

  const activeScene = videoStoryboard[activeSceneIdx] || videoStoryboard[0];

  const handleGenerate = (e) => {
    e.preventDefault();
    if (!promptTopic.trim()) return;
    setIsGenerating(true);
    showNotification(`Generating video lesson for "${promptTopic}"...`);
    setTimeout(() => {
      setIsGenerating(false);
      showNotification(`Video lesson for "${promptTopic}" is ready to watch!`);
    }, 1800);
  };

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">AI VIDEO LESSON STUDIO</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Video Lesson Studio</h1>
            <p className="page-subheading">
              Watch generated video lessons and walkthroughs derived from your textbook chapters.
            </p>
          </div>
          <div className="header-actions">
            <button 
              type="button" 
              className="btn-atelier-outline"
              onClick={() => showNotification('Video downloaded successfully (MP4 1080p).')}
            >
              <span>Download MP4</span>
            </button>
            <button 
              type="button" 
              className="btn-atelier-primary"
              onClick={() => navigate('/app/assessment')}
            >
              <span>Practice This Topic</span>
              <GlyphCheckmark size={12} />
            </button>
          </div>
        </div>

        {/* Quick Topic Video Generator Bar */}
        <form onSubmit={handleGenerate} className="video-generator-input-form" style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input 
              type="text" 
              value={promptTopic}
              onChange={(e) => setPromptTopic(e.target.value)}
              placeholder="Enter any topic or concept to generate a video lesson..."
              className="atelier-text-input"
              style={{ flex: 1 }}
            />
            <button 
              type="submit" 
              className="btn-atelier-primary"
              disabled={isGenerating}
            >
              <GlyphPlay size={12} />
              <span>{isGenerating ? 'Generating Video...' : 'Generate New Video'}</span>
            </button>
          </div>
        </form>
      </section>

      {/* Main 2-Column Grid: 16:9 Video Player & Storyboard Chapters */}
      <div className="video-studio-grid">
        {/* Left Column: Player Stage */}
        <div className="video-viewport-column">
          <div className="atelier-card video-stage-card">
            <div className="card-top-bar">
              <span className="coord-label">CHAPTER {activeScene.sceneIndex} · {activeScene.time}</span>
              <span className="card-badge-soft">HD 1080P</span>
            </div>

            <div className="vector-player-stage">
              <img 
                src={activeScene.plate} 
                alt={activeScene.title} 
                className="vector-poster-media" 
              />
              
              <div className="vector-stage-overlay">
                <button 
                  type="button" 
                  className="stage-play-button"
                  onClick={() => setIsPlaying(!isPlaying)}
                  aria-label={isPlaying ? 'Pause' : 'Play'}
                >
                  {isPlaying ? <GlyphPause size={22} /> : <GlyphPlay size={22} />}
                </button>
              </div>

              <div className="vector-formula-caption">
                <span className="coord-label">TOPIC OVERVIEW:</span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', fontWeight: 600, color: '#FFFFFF', marginLeft: '6px' }}>
                  {activeScene.title}
                </span>
              </div>
            </div>

            {/* Scrubber & Player Controls */}
            <div className="studio-controls-bar">
              <button 
                type="button" 
                className="control-icon-btn"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <GlyphPause size={14} /> : <GlyphPlay size={14} />}
              </button>

              <div className="scrubber-track-container">
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={currentProgress}
                  onChange={(e) => setCurrentProgress(Number(e.target.value))}
                  className="studio-scrubber-slider"
                />
              </div>

              <span className="playback-timestamp mono">
                00:{currentProgress < 10 ? `0${currentProgress}` : currentProgress} / 01:30
              </span>

              <span className="quality-pill">HD 1080P</span>
            </div>

            <div className="video-stage-meta-strip">
              <span className="coord-label">CURRENT LESSON:</span>
              <strong className="scene-name-tag">{activeScene.title}</strong>
              <button 
                type="button" 
                className="btn-atelier-outline"
                disabled={isGenerating}
                onClick={() => {
                  showNotification('Re-rendering video frames...');
                  setTimeout(() => showNotification('Video updated successfully.'), 1200);
                }}
                style={{ marginLeft: 'auto' }}
              >
                <GlyphRotate size={12} />
                <span>Replay Lesson</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Lesson Chapters & Key Takeaways (Python code removed!) */}
        <div className="video-code-column">
          <div className="atelier-card storyboard-deck-card">
            <div className="card-top-bar">
              <span className="coord-label">LESSON CHAPTERS (4 PARTS)</span>
              <span className="card-badge-soft">TIMELINE</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '14px' }}>
              {videoStoryboard.map((scene, idx) => {
                const isSelected = activeSceneIdx === idx;
                return (
                  <div 
                    key={scene.sceneIndex}
                    className={`storyboard-scene-chip ${isSelected ? 'active' : ''}`}
                    onClick={() => setActiveSceneIdx(idx)}
                    style={{
                      cursor: 'pointer',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sharp)',
                      border: isSelected ? '1px solid var(--terracotta)' : '1px solid var(--border)',
                      backgroundColor: isSelected ? 'rgba(164, 96, 71, 0.08)' : 'var(--surface-panel)',
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'center'
                    }}
                  >
                    <div style={{ width: '64px', height: '44px', overflow: 'hidden', borderRadius: '2px', position: 'relative' }}>
                      <img src={scene.thumb} alt={scene.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      <span style={{
                        position: 'absolute',
                        bottom: '2px',
                        right: '2px',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        color: '#FFF',
                        fontSize: '9px',
                        fontFamily: 'var(--font-mono)',
                        padding: '1px 3px'
                      }}>
                        {scene.sceneIndex}
                      </span>
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                        <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--ink-muted)' }}>
                          {scene.time}
                        </span>
                        {isSelected && (
                          <span style={{ fontSize: '9px', color: 'var(--terracotta)', fontWeight: 600 }}>
                            NOW PLAYING
                          </span>
                        )}
                      </div>
                      <strong style={{ fontSize: '13px', color: 'var(--ink-primary)', display: 'block', lineHeight: 1.3 }}>
                        {scene.title}
                      </strong>
                      <p style={{ fontSize: '11px', color: 'var(--ink-muted)', marginTop: '2px', lineHeight: 1.3 }}>
                        {scene.summary}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ padding: '14px', borderTop: '1px solid var(--border)' }}>
              <div style={{ marginBottom: '10px' }}>
                <span className="coord-label" style={{ display: 'block', marginBottom: '4px' }}>SUMMARY KEY TAKEAWAYS:</span>
                <p style={{ fontSize: '12.5px', color: 'var(--ink-secondary)', lineHeight: 1.5 }}>
                  This video demonstrates how primary key constraints prevent duplicate entries and why database engines forbid null values in identity columns.
                </p>
              </div>

              <button 
                type="button" 
                className="btn-atelier-primary"
                onClick={() => navigate('/app/studio')}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <span>Open in Study Studio with Notes</span>
                <GlyphArrowRight size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
