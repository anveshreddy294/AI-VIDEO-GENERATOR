import React from 'react';
import { Navigate } from 'react-router-dom';

// Kept as a compatibility entry point for bookmarks and old internal links.
// Practice now belongs to the active lesson workspace.
export default function AssessmentPage() {
  return <Navigate to="/app/studio?tab=practice" replace />;
}
