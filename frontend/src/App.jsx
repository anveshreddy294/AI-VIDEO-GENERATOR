import { useState } from 'react';
import { ProfileProvider, useProfile } from './context/ProfileContext';
import { SessionProvider } from './context/SessionContext';

// Import Screens
import Landing from './screens/Landing';
import Onboarding from './screens/Onboarding';
import Dashboard from './screens/Dashboard';
import Workspace from './screens/Workspace';
import Library from './screens/Library';
import KnowledgeGraph from './screens/KnowledgeGraph';
import Analytics from './screens/Analytics';
import ScriptInspector from './screens/ScriptInspector';
import Profile from './screens/Profile';
import Health from './screens/Health';

// Import Common Components
import Sidebar from './components/Sidebar';

function AppContent() {
  const { profile, loading } = useProfile();
  
  // Navigation states
  const [showLanding, setShowLanding] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [activeScreen, setActiveScreen] = useState('dashboard');

  if (loading) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          background: 'var(--bg-base)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          color: 'var(--text-primary)',
          fontSize: '18px',
          fontFamily: 'var(--font-ui)',
          letterSpacing: '0.05em'
        }}
      >
        <div className="generating" style={{ padding: 'var(--space-6) var(--space-10)', borderRadius: 'var(--r-md)' }}>
          Bootstrapping LearnOS Terminal...
        </div>
      </div>
    );
  }

  // S-01 Cinematic Landing page view
  if (showLanding) {
    return (
      <Landing
        onStart={() => {
          setShowLanding(false);
          // If learner has not been configured (no name), route them to onboarding. Otherwise, go to dashboard.
          if (!profile.name || profile.name.trim() === '') {
            setShowOnboarding(true);
          } else {
            setActiveScreen('dashboard');
          }
        }}
      />
    );
  }

  // S-02 Conversational Onboarding profiling view
  if (showOnboarding) {
    return (
      <Onboarding
        onComplete={() => {
          setShowOnboarding(false);
          setActiveScreen('dashboard');
        }}
      />
    );
  }

  // Helper function to render active dashboard widget screen
  const renderScreen = () => {
    switch (activeScreen) {
      case 'dashboard':
        return <Dashboard setActiveScreen={setActiveScreen} />;
      case 'workspace':
        return <Workspace />;
      case 'library':
        return <Library setActiveScreen={setActiveScreen} />;
      case 'graph':
        return <KnowledgeGraph setActiveScreen={setActiveScreen} />;
      case 'analytics':
        return <Analytics />;
      case 'inspector':
        return <ScriptInspector />;
      case 'profile':
        return <Profile />;
      case 'health':
        return <Health />;
      default:
        return <Dashboard setActiveScreen={setActiveScreen} />;
    }
  };

  return (
    <div className="learnos-layout">
      {/* Persistent global Navigation drawer sidebar */}
      <Sidebar activeScreen={activeScreen} setActiveScreen={setActiveScreen} />

      {/* Primary layout content canvas viewport */}
      <div style={{ flex: 1, height: '100%', overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
        {renderScreen()}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ProfileProvider>
      <SessionProvider>
        <AppContent />
      </SessionProvider>
    </ProfileProvider>
  );
}
