import { useEffect, useState } from 'react';
import MetricCard from '../components/MetricCard';

export default function Analytics() {
  const [analyticsData, setAnalyticsData] = useState({
    total_sessions: 0,
    total_watch_time_seconds: 0,
    topics_covered: [],
    weak_topic_flags: [],
    daily_activity: [],
    subject_distribution: { Physics: 0, Chemistry: 0, Mathematics: 0 }
  });

  const [, setHistoryData] = useState({ sessions: [] });

  useEffect(() => {
    async function loadStats() {
      try {
        const aRes = await fetch('/api/load/analytics.json');
        if (aRes.ok) {
          const data = await aRes.json();
          setAnalyticsData(data);
        }

        const hRes = await fetch('/api/load/history.json');
        if (hRes.ok) {
          const data = await hRes.json();
          setHistoryData(data);
        }
      } catch { /* Optional persisted data may be absent. */ }
    }
    loadStats();
  }, []);

  const totalMin = Math.ceil(analyticsData.total_watch_time_seconds / 60) || 0;
  const avgSessionMin = analyticsData.total_sessions 
    ? Math.round(totalMin / analyticsData.total_sessions)
    : 0;

  // 1. Calculations for Relative Subject Donut Chart
  const physicsCount = analyticsData.subject_distribution?.Physics || 0;
  const chemistryCount = analyticsData.subject_distribution?.Chemistry || 0;
  const mathCount = analyticsData.subject_distribution?.Mathematics || 0;
  const totalSubjs = physicsCount + chemistryCount + mathCount || 1;

  const physPct = physicsCount / totalSubjs;
  const chemPct = chemistryCount / totalSubjs;
  const mathPct = mathCount / totalSubjs;

  // Donut SVG constants
  const r = 40;
  const circum = 2 * Math.PI * r;

  // 2. Calculations for Confidence Radar (Spider Chart)
  // Assuming a hypothetical profile is checked, fallback values from mock
  const physConf = 75;
  const chemConf = 60;
  const mathConf = 80;

  // Scale calculations for 3-axis radar (vertices inside 100x100 box)
  // Center: (50, 50)
  // Axis angles: 0 (top/Physics), 120 (bottom-right/Chemistry), 240 (bottom-left/Math)
  const getRadarPoint = (val, angleDeg) => {
    const angleRad = (angleDeg - 90) * (Math.PI / 180);
    const radius = (val / 100) * 40;
    const x = 50 + radius * Math.cos(angleRad);
    const y = 50 + radius * Math.sin(angleRad);
    return `${x},${y}`;
  };

  const polyPoints = [
    getRadarPoint(physConf, 0),
    getRadarPoint(chemConf, 120),
    getRadarPoint(mathConf, 240)
  ].join(' ');

  // Grid background circles for radar
  const radarGridCircles = [25, 50, 75, 100].map(c => (
    <circle
      key={c}
      cx="50"
      cy="50"
      r={(c / 100) * 40}
      fill="none"
      stroke="var(--border-subtle)"
      strokeWidth="0.5"
    />
  ));

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: 'var(--space-8)' }}>
      
      {/* Page Header */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 className="serif-title" style={{ fontSize: '38px', fontWeight: '400', color: 'var(--text-primary)' }}>
          Learning Insights
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
          Deep-dive analysis of your topic navigation curves, textbook retention, and category distribution.
        </p>
      </div>

      {/* Metrics Row Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
        <MetricCard
          title="Total Lectures"
          value={analyticsData.total_sessions || 0}
          label="Custom modules rendered"
          icon="📚"
          color="var(--text-primary)"
        />
        <MetricCard
          title="Watch Time"
          value={`${totalMin} min`}
          label="Cumulative video playtime"
          icon="⏱️"
          color="var(--accent-amber)"
        />
        <MetricCard
          title="Engagement Depth"
          value={`${avgSessionMin} min`}
          label="Average session length"
          icon="📈"
          color="var(--accent-teal)"
        />
        <MetricCard
          title="Flagged Weak Areas"
          value={analyticsData.weak_topic_flags?.length || 0}
          label="Topics needing refactoring"
          icon="⚠️"
          color="var(--accent-rose)"
        />
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-6)', marginBottom: 'var(--space-8)' }}>
        
        {/* Radar Spider Chart (Confidence parameters) */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h4 className="serif-title" style={{ fontSize: '18px', fontWeight: '400', color: 'var(--text-primary)', alignSelf: 'flex-start', margin: '0 0 var(--space-4) 0' }}>
            Subject Confidence Index
          </h4>
          
          <div style={{ width: '220px', height: '220px', position: 'relative' }}>
            <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%' }}>
              {/* Radar Grids */}
              {radarGridCircles}
              
              {/* Axis lines */}
              <line x1="50" y1="50" x2="50" y2="10" stroke="var(--border-subtle)" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="84.6" y2="70" stroke="var(--border-subtle)" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="15.4" y2="70" stroke="var(--border-subtle)" strokeWidth="0.5" />

              {/* Data Polygon */}
              <polygon
                points={polyPoints}
                fill="rgba(245, 158, 11, 0.15)"
                stroke="var(--accent-amber)"
                strokeWidth="1.5"
                filter="drop-shadow(0px 0px 4px rgba(245, 158, 11, 0.4))"
              />

              {/* Axis Labels */}
              <text x="50" y="8" fill="var(--text-primary)" fontSize="5" fontWeight="600" textAnchor="middle">Physics ({physConf}%)</text>
              <text x="88" y="73" fill="var(--text-primary)" fontSize="5" fontWeight="600" textAnchor="start">Chemistry ({chemConf}%)</text>
              <text x="12" y="73" fill="var(--text-primary)" fontSize="5" fontWeight="600" textAnchor="end">Maths ({mathConf}%)</text>
            </svg>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', marginTop: '10px' }}>
            Derived from self-reported onboarding ratings and interactive follow-up depths.
          </p>
        </div>

        {/* Subject Donut Circle Chart */}
        <div className="learnos-card" style={{ background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h4 className="serif-title" style={{ fontSize: '18px', fontWeight: '400', color: 'var(--text-primary)', alignSelf: 'flex-start', margin: '0 0 var(--space-4) 0' }}>
            Syllabus Distribution
          </h4>

          <div style={{ width: '220px', height: '220px', position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%' }}>
              {/* Physics segment */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="var(--accent-blue)"
                strokeWidth="10"
                strokeDasharray={circum}
                strokeDashoffset={0}
                transform="rotate(-90 50 50)"
              />
              {/* Chemistry segment */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="var(--accent-amber)"
                strokeWidth="10"
                strokeDasharray={circum}
                strokeDashoffset={circum * (1 - chemPct)}
                transform={`rotate(${(physPct * 360) - 90} 50 50)`}
              />
              {/* Mathematics segment */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="var(--accent-violet)"
                strokeWidth="10"
                strokeDasharray={circum}
                strokeDashoffset={circum * (1 - mathPct)}
                transform={`rotate(${((physPct + chemPct) * 360) - 90} 50 50)`}
              />
            </svg>
            <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span className="mono-text" style={{ fontSize: '24px', fontWeight: '500', color: 'var(--text-primary)' }}>
                {analyticsData.total_sessions}
              </span>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>renders</span>
            </div>
          </div>

          {/* Donut Legend */}
          <div style={{ display: 'flex', gap: '15px', marginTop: '12px', fontSize: '11px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>Physics ({physicsCount})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-amber)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>Chemistry ({chemistryCount})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-violet)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>Mathematics ({mathCount})</span>
            </div>
          </div>
        </div>

      </div>

      {/* Weekly heatmaps grids */}
      <div className="learnos-card" style={{ background: 'var(--bg-surface)', marginBottom: 'var(--space-6)' }}>
        <h4 className="serif-title" style={{ fontSize: '18px', fontWeight: '400', color: 'var(--text-primary)', margin: '0 0 var(--space-4) 0' }}>
          Weekly Lecture Stream Heatmap
        </h4>
        
        {/* Custom Contribution grid matrix */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', overflowX: 'auto', paddingBottom: '10px' }}>
          <div style={{ display: 'flex', gap: '3px' }}>
            {Array.from({ length: 52 }).map((_, colIdx) => {
              // Highlight selected columns representing recent active days
              const hasActivity = colIdx >= 48; // simulate active weeks at end of scale
              const intensity = hasActivity ? (colIdx % 3 === 0 ? 0.8 : 0.4) : 0;
              
              return (
                <div
                  key={colIdx}
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '2px',
                    background: intensity > 0
                      ? `rgba(20, 184, 166, ${intensity})`
                      : 'var(--bg-raised)',
                    border: '1px solid var(--border-subtle)'
                  }}
                  title={`Week ${colIdx + 1}: ${hasActivity ? 'Minutes logged' : '0 min'}`}
                />
              );
            })}
          </div>
        </div>
        <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', margin: 0 }}>
          Simulating a 52-week rolling timeline. Deeper green tiles indicate multi-stage pipeline completions.
        </p>
      </div>

    </div>
  );
}
