
export default function GenerationShimmer({ rows = 3, height = '20px', style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', width: '100%', ...style }}>
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className="generating"
          style={{
            height,
            borderRadius: 'var(--r-sm)',
            width: idx === rows - 1 && rows > 1 ? '60%' : '100%',
            opacity: 1 - (idx * 0.15) // Subtle fading for staggered layout look
          }}
        />
      ))}
    </div>
  );
}
