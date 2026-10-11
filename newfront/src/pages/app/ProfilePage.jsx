import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { toUserMessage } from '../../services/api/errors';

export default function ProfilePage() {
  const { user, logout } = useAtelierWorkspace();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const signOut = async () => {
    setBusy(true);
    try { await logout(); } catch (requestError) { setError(requestError); } finally { setBusy(false); }
  };
  return <div className="workspace-page-root">
    <section className="atelier-page-header"><span className="coord-label">YOUR ACCOUNT</span><h1 className="page-heading">Profile</h1><p className="page-subheading">Your account details and workspace preferences.</p></section>
    <section className="user-identity-card">
      <div className="identity-badge-mount"><span className="user-avatar-tag">{user.avatarLabel}</span><div className="identity-names"><h2 className="identity-name">{user.name}</h2><p className="identity-email">{user.email}</p></div></div>
      <dl className="profile-details"><div><dt>Account role</dt><dd>{user.backendRole || user.role}</dd></div>{user.course && <div><dt>Course</dt><dd>{user.course}</dd></div>}</dl>
      {error && <p role="alert">{toUserMessage(error)}</p>}
      <div className="identity-card-actions"><button type="button" className="btn-atelier-outline" onClick={signOut} disabled={busy}>{busy ? 'Signing out…' : 'Sign Out'}</button></div>
    </section>
    <section className="unboxed-content-section"><h2>Accessibility</h2><p>VisualAI follows your device’s reduced-motion preference. Keyboard focus is highlighted throughout the workspace.</p></section>
    <section className="unboxed-content-section"><h2>Your saved work</h2><p>Lessons and materials stay in your account when you sign out. Review how account data is handled in our policy drafts.</p><div className="legal-links"><Link to="/terms">Terms of Service</Link><Link to="/privacy">Privacy Policy</Link></div></section>
  </div>;
}
