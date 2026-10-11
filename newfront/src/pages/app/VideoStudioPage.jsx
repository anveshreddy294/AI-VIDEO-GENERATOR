import React from 'react';
import { Navigate } from 'react-router-dom';

// Kept as a compatibility entry point for bookmarks and old internal links.
// Video now belongs to the active lesson workspace.
export default function VideoStudioPage() {
  return <Navigate to="/app/studio?tab=video" replace />;
}
