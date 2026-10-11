import React from 'react';
import { Link } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';

export default function EducatorHubPage() {
  const { user } = useAtelierWorkspace();
  return <div className="workspace-page-root">
    <section className="atelier-page-header"><span className="coord-label">EDUCATOR WORKSPACE</span><h1 className="page-heading">Teaching resources</h1><p className="page-subheading">Signed in as {user.backendRole || user.role}. Prepare material and review lessons in your workspace.</p></section>
    <section className="unboxed-content-section"><h2>Prepare a lesson</h2><p>Upload your study material, then create a lesson using the available content.</p><div className="legal-links"><Link to="/app/library" className="btn-atelier-primary">Open My Materials</Link><Link to="/app/explore" className="btn-atelier-outline">Open My Learning</Link></div></section>
    <section className="unboxed-content-section"><h2>Cohort reporting</h2><p>Cohort analytics and institutional integrations are not connected to this view. No class-wide results are available here.</p></section>
  </div>;
}
