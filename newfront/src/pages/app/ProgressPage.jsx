import React from 'react';
import { Link } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { LoadingContent } from '../../components/ui/Skeleton';

export default function ProgressPage() {
  const { activeLesson, workspaceStatus } = useAtelierWorkspace();
  const submissions = activeLesson?.submissions || [];
  return <div className="workspace-page-root">
    <section className="atelier-page-header"><span className="coord-label">YOUR PRACTICE</span><h1 className="page-heading">Learning progress</h1><p className="page-subheading">Review saved assessment results for your current lesson.</p></section>
    {workspaceStatus === 'loading' ? <LoadingContent label="Loading results…" /> : <section className="unboxed-content-section">
      <h2>{activeLesson?.topic || 'Choose a lesson'}</h2>
      {submissions.length ? submissions.map((submission, index) => <article className="modern-dashboard-list-row" key={submission.submission_id || index}><div><strong>Attempt {index + 1}</strong><p>{submission.feedback}</p></div><strong>{submission.percentage == null ? 'Score unavailable' : `${submission.percentage}%`}</strong></article>) : <p>No saved assessment results for this lesson yet.</p>}
      <div><Link to={activeLesson ? '/app/studio?tab=practice' : '/app/explore'} className="btn-atelier-primary">{activeLesson ? 'Open Practice' : 'Open My Learning'}</Link></div>
    </section>}
  </div>;
}
