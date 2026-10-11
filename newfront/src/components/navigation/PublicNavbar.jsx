import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { GlyphBrandMark, GlyphArrowRight } from '../ui/AtelierGlyphs';

export default function PublicNavbar() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

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
        <button type="button" className="public-menu-button btn-atelier-outline" aria-expanded={menuOpen} aria-controls="public-navigation" onClick={() => setMenuOpen(!menuOpen)}>Menu</button>
        <nav id="public-navigation" className={`navbar-links ${menuOpen ? 'open' : ''}`} aria-label="Public Navigation" onKeyDown={event => { if (event.key === 'Escape') { setMenuOpen(false); document.querySelector('.public-menu-button')?.focus(); } }}>
          {navLinks.map(link => {
            const isActive = location.pathname === link.path;
            return (
              <Link 
                key={link.path} 
                to={link.path} 
                className={`nav-link ${isActive ? 'active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
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
