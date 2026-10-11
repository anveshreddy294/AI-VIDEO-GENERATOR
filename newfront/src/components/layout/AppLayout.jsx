import React, { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphBrandMark, 
  GlyphDocument,
  GlyphEvidence,
  GlyphDag,
  GlyphUser, 
  GlyphGrid
} from '../ui/AtelierGlyphs';

export default function AppLayout() {
  const { user, activeSource, activeConcept, notification } = useAtelierWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const navItems = [
    { label: 'Dashboard', path: '/app/dashboard', glyph: GlyphGrid, desc: 'Choose what to learn next' },
    { label: 'My Learning', path: '/app/explore', glyph: GlyphEvidence, desc: 'Create or resume a lesson' },
    { label: 'My Materials', path: '/app/library', glyph: GlyphDocument, desc: 'Upload and view study material' },
    { label: 'Learning Workspace', path: '/app/studio', glyph: GlyphDag, desc: 'Learn, practice, ask and watch' },
    { label: 'Profile', path: '/app/profile', glyph: GlyphUser, desc: 'Account and preferences' }
  ];

  return (
    <div className="atelier-app-root">
      {/* Toast Notification */}
      {notification && (
        <div className="atelier-toast-banner" role="status">
          <span className="toast-dot" />
          <span className="toast-message">{notification}</span>
        </div>
      )}

      {/* Top Application Bar */}
      <header className="app-top-bar">
        <div className="app-top-left">
          <button 
            type="button"
            className="app-brand-lockup-btn"
            onClick={() => setSidebarOpen(prev => !prev)}
            title="Click to open left workspace toolbar"
            style={{
              background: 'none',
              border: 'none',
              padding: '4px 6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              color: 'inherit',
              textAlign: 'left',
              borderRadius: 'var(--radius-sharp)'
            }}
          >
            <GlyphBrandMark size={18} className="brand-glyph" />
            <span className="brand-title" style={{ fontWeight: 600, fontSize: '15px' }}>VisualAI</span>
            <span className="app-breadcrumb-sep">/</span>
            <span className="app-role-pill">{user.role === 'educator' ? 'INSTRUCTOR CONSOLE' : 'STUDENT WORKSPACE'}</span>
            <span style={{ 
              fontSize: '11px', 
              padding: '2px 6px', 
              borderRadius: 'var(--radius-sharp)',
              backgroundColor: sidebarOpen ? 'var(--terracotta)' : 'var(--surface-subtle)',
              color: sidebarOpen ? '#FFFFFF' : 'var(--ink-secondary)',
              marginLeft: '4px',
              fontWeight: 600
            }}>
              {sidebarOpen ? '✕' : '☰'}
            </span>
          </button>
        </div>

        <div className="app-top-center">
          <div className="app-context-crumb">
              <span className="crumb-source">{activeConcept?.title || activeSource?.name || 'Choose something to learn'}</span>
              {activeConcept && <><span className="crumb-sep">·</span><span className="crumb-concept">Learning Workspace</span></>}
          </div>
        </div>

        <div className="app-top-right">
          <span className="app-telemetry-chip" style={{ marginRight: '8px' }}>
            <span className="status-live-beacon" style={{ width: '6px', height: '6px', margin: 0 }} />
            <span>37°N · v3.0</span>
          </span>
          <Link to="/app/profile" className="app-user-pill">
            <span className="user-avatar-tag">{user.avatarLabel}</span>
            <span className="user-name-tag">{user.name}</span>
          </Link>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="app-body-container">
        {/* Backdrop for Left Slide-In Toolbar */}
        {sidebarOpen && (
          <div 
            className="app-sidebar-backdrop open" 
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Left Architectural Navigation Toolbar (Opens when VisualAI is clicked) */}
        <aside className={`app-sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div className="sidebar-section-title" style={{ margin: 0, padding: 0 }}>
              {user.role === 'educator' ? 'INSTRUCTOR CONSOLE' : 'STUDENT WORKSPACE'}
            </div>
            <button 
              type="button"
              onClick={() => setSidebarOpen(false)}
              title="Close toolbar"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--ink-muted)',
                fontSize: '14px',
                padding: '2px 6px'
              }}
            >
              ✕
            </button>
          </div>

          <nav className="sidebar-nav-list">
            {navItems.map(item => {
              const isActive = location.pathname === item.path;
              const Icon = item.glyph;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                >
                  <Icon size={14} className="sidebar-glyph" />
                  <span className="sidebar-label">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {user.role === 'educator' && (
            <div className="sidebar-educator-dock">
              <div className="sidebar-section-title">GOVERNANCE & ANALYTICS</div>
              <Link 
                to="/educator" 
                onClick={() => setSidebarOpen(false)}
                className={`sidebar-nav-item ${location.pathname === '/educator' ? 'active' : ''}`}
              >
                <GlyphDag size={14} className="sidebar-glyph" />
                <span className="sidebar-label">Educator Analytics</span>
              </Link>
            </div>
          )}

          <div className="sidebar-bottom-info">
            <Link 
              to="/" 
              onClick={() => setSidebarOpen(false)}
              style={{ 
                display: 'block',
                fontSize: '11px', 
                color: 'var(--terracotta)', 
                textDecoration: 'none', 
                fontWeight: 600,
                marginBottom: '10px'
              }}
            >
              ← Exit to Home
            </Link>
            <div className="sidebar-system-spec">
              <span>CANONICAL SANDBOX</span>
              <span>v0.4.0 · OPTICAL PROVENANCE</span>
            </div>
          </div>
        </aside>

        {/* Right Main Content Canvas (Full width when sidebar is closed) */}
        <main className="app-main-canvas">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
