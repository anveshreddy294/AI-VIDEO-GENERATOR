import { useProfile } from '../context/ProfileContext';
import { useSession } from '../context/SessionContext';

export default function Sidebar({ activeScreen, setActiveScreen }) {
  const { profile } = useProfile();
  const { newSession } = useSession();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '⚡' },
    { id: 'workspace', label: 'Workspace', icon: '🎓' },
    { id: 'library', label: 'Video Library', icon: '📁' },
    { id: 'graph', label: 'Knowledge Graph', icon: '🕸️' },
    { id: 'analytics', label: 'Analytics & Stats', icon: '📊' },
    { id: 'inspector', label: 'Script Inspector', icon: '🐍' },
    { id: 'profile', label: 'Profile Settings', icon: '⚙️' },
    { id: 'health', label: 'Pipeline Monitor', icon: '❤️' }
  ];

  return (
    <div
      style={{
        width: '260px',
        height: '100%',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        flexShrink: 0
      }}
    >
      {/* Top User Profile Header */}
      <div style={{ padding: 'var(--space-6)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: 'var(--accent-amber-dim)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px',
              color: 'var(--accent-amber)',
              fontWeight: '600'
            }}
          >
            {profile.name ? profile.name[0].toUpperCase() : 'U'}
          </div>
          <div>
            <h4 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: '600' }}>
              {profile.name || 'LearnOS Guest'}
            </h4>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {profile.academic_level?.replace('_', ' ')}
            </span>
          </div>
        </div>
      </div>

      {/* Main Navigation Item List */}
      <div style={{ flex: 1, padding: 'var(--space-4) var(--space-3)', display: 'flex', flexDirection: 'column', gap: '4px', overflowY: 'auto' }}>
        <button
          onClick={async () => {
            await newSession();
            setActiveScreen('workspace');
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-2)',
            padding: 'var(--space-3) var(--space-4)',
            marginBottom: 'var(--space-2)',
            borderRadius: 'var(--r-md)',
            color: 'var(--text-primary)',
            background: 'var(--bg-raised)',
            border: '1px solid var(--border-default)',
            fontFamily: 'var(--font-ui)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: '16px' }}>＋</span>
          <span>New Lesson</span>
        </button>

        {navItems.map(item => {
          const isActive = activeScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveScreen(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-3) var(--space-4)',
                borderRadius: 'var(--r-md)',
                color: isActive ? 'var(--accent-amber)' : 'var(--text-secondary)',
                background: isActive ? 'var(--bg-raised)' : 'transparent',
                border: 'none',
                fontFamily: 'var(--font-ui)',
                fontSize: '14px',
                fontWeight: isActive ? 600 : 400,
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--text-primary)';
                  e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--text-secondary)';
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              <span style={{ fontSize: '16px' }}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Footer info branding */}
      <div style={{ padding: 'var(--space-4) var(--space-6)', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
          LearnOS v1.0
        </span>
      </div>
    </div>
  );
}
