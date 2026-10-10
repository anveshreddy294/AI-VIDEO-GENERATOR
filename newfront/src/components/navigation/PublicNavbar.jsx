import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { GlyphBrandMark, GlyphArrowRight } from '../ui/AtelierGlyphs';

export default function PublicNavbar() {
  const location = useLocation();

  const navLinks = [
    { label: 'Platform', path: '/platform' },
    { label: 'How It Works', path: '/how-it-works' },
    { label: 'Product Demo', path: '/demo' },
    { label: 'Architecture', path: '/architecture' },
    { label: 'About', path: '/about' }
  ];

  return (
    <header className="atelier-navbar">
      <div className="atelier-container navbar-inner">
        {/* Brand Lockup */}
        <Link to="/" className="brand-lockup">
          <GlyphBrandMark size={22} className="brand-glyph" />
          <div className="brand-text-block">
            <span className="brand-name">VisualAI</span>
            <span className="brand-atelier-tag">THE KNOWLEDGE ATELIER</span>
          </div>
        </Link>

        {/* Center Editorial Links */}
        <nav className="navbar-links" aria-label="Public Navigation">
          {navLinks.map(link => {
            const isActive = location.pathname === link.path;
            return (
              <Link 
                key={link.path} 
                to={link.path} 
                className={`nav-link ${isActive ? 'active' : ''}`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right Action Units */}
        <div className="navbar-actions">
          <Link to="/app/dashboard" className="nav-workspace-link">
            Open Workspace
          </Link>
          <Link to="/signin" className="btn-atelier-primary">
            <span>Start Learning</span>
            <GlyphArrowRight size={12} />
          </Link>
        </div>
      </div>
    </header>
  );
}
