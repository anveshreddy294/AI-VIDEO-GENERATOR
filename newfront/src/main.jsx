import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { WorkspaceProvider } from './context/WorkspaceContext';

// Foundational Architectural Design Tokens and Stylesheets
import './styles/tokens.css';
import './styles/reset.css';
import './styles/atelier.css';

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <WorkspaceProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </WorkspaceProvider>
    </React.StrictMode>
  );
}
