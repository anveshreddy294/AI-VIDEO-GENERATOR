
const SUBJECT_THEMES = {
  physics: 'badge-blue',
  chemistry: 'badge-teal',
  mathematics: 'badge-violet',
  biology: 'badge-rose',
  general: 'badge-amber'
};

export default function SubjectPill({ subject }) {
  const normalized = subject?.toLowerCase() || 'general';
  const themeClass = SUBJECT_THEMES[normalized] || 'badge-gray';

  return (
    <span className={`badge ${themeClass}`} style={{ fontSize: '11px', letterSpacing: '0.04em' }}>
      {subject || 'General'}
    </span>
  );
}
