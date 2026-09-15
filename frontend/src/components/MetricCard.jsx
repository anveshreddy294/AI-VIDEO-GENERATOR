
export default function MetricCard({ title, value, label, icon, color = 'var(--text-primary)' }) {
  return (
    <div className="learnos-card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', minWidth: '180px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)' }}>
          {title}
        </span>
        <span style={{ fontSize: '18px', color }}>
          {icon}
        </span>
      </div>
      <div className="serif-title" style={{ fontSize: '36px', color, lineHeight: '1', margin: '4px 0' }}>
        {value}
      </div>
      {label && (
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {label}
        </span>
      )}
    </div>
  );
}
