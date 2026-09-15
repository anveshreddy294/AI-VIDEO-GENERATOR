import { useEffect, useState } from 'react';
import { useProfile } from '../context/ProfileContext';
import { useSession } from '../context/SessionContext';
import MetricCard from '../components/MetricCard';
import SubjectPill from '../components/SubjectPill';
import topicCatalog from '../mock/topic_catalog.json';
import {
  formatSessionDate,
  getSessionsThisWeek,
  computeActiveStreak,
} from '../utils/sessionHelpers';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000';

const _STATIC_SUBJECT_DOC_MAP = {
  Chemistry: 'Chemistry.pdf',
  Physics: 'physics.pdf',
};

export default function Dashboard({ setActiveScreen }) {
  const { profile } = useProfile();
  const { startPipeline, loadSessionById } = useSession();
  const [historyData, setHistoryData] = useState({ sessions: [] });
  const [analyticsData, setAnalyticsData] = useState({
    total_sessions: 0,
    total_watch_time_seconds: 0,
    topics_covered: [],
    weak_topic_flags: [],
    daily_activity: [],
    subject_distribution: {}
  });

  const [greeting, setGreeting] = useState('Welcome');
  const [sortedSuggestions, setSortedSuggestions] = useState([]);
  const [subjectDocMap, setSubjectDocMap] = useState(_STATIC_SUBJECT_DOC_MAP);

  // Fetch indexed documents and build subject → docId map dynamically.
  useEffect(() => {
    async function fetchDocMap() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/curriculum/documents`);
        if (!res.ok) return;
        const data = await res.json();
        const docs = data.documents || [];
        const map = {};
        for (const doc of docs) {
          if (doc.subject && doc.id && doc.indexed !== false) {
            map[doc.subject] = doc.id;
          }
        }
        if (Object.keys(map).length > 0) {
          setSubjectDocMap(map);
        }
      } catch {
        // Fall back to static map silently.
      }
    }
    fetchDocMap();
  }, []);

  // Time-aware greeting
  useEffect(() => {
    const hr = new Date().getHours();
    if (hr < 12) setGreeting('Good morning');
    else if (hr < 17) setGreeting('Good afternoon');
    else setGreeting('Good evening');
  }, []);

  // Fetch history and analytics
  useEffect(() => {
    async function loadStats() {
      try {
        const hRes = await fetch('/api/load/history.json');
        if (hRes.ok) {
          const data = await hRes.json();
          setHistoryData(data);
        }
        
        const aRes = await fetch('/api/load/analytics.json');
        if (aRes.ok) {
          const data = await aRes.json();
          setAnalyticsData(data);
        }
      } catch (err) {
        console.warn('Failed to load dashboard metrics:', err);
      }
    }
    loadStats();
  }, []);

  // Sort topic suggestions based on learner confidence mapping
  useEffect(() => {
    if (!topicCatalog?.topics) return;

    const chemConf = profile.confidence_map?.Chemistry || 50;
    const physConf = profile.confidence_map?.Physics || 50;
    const mathConf = profile.confidence_map?.Mathematics || 50;

    // Find the weakest subject
    let weakSubject = 'Chemistry';
    let minVal = chemConf;

    if (physConf < minVal) {
      weakSubject = 'Physics';
      minVal = physConf;
    }
    if (mathConf < minVal) {
      weakSubject = 'Mathematics';
    }

    // Sort: topics matching weakest subject come first
    const sorted = [...topicCatalog.topics].sort((a, b) => {
      if (a.subject === weakSubject && b.subject !== weakSubject) return -1;
      if (b.subject === weakSubject && a.subject !== weakSubject) return 1;
      return 0;
    });

    setSortedSuggestions(sorted);
  }, [profile]);

  const handleSuggestionClick = async (topicTitle, subject) => {
    setActiveScreen('workspace');
    const docId = subjectDocMap[subject] || null;
    await startPipeline(topicTitle, subject, docId);
  };

  const handleContinueClick = async (sid) => {
    setActiveScreen('workspace');
    await loadSessionById(sid);
  };

  // Compute stats helper
  const totalWatchMin = Math.ceil(analyticsData.total_watch_time_seconds / 60);
  const totalWatchTimeText = totalWatchMin >= 60 
    ? `${Math.floor(totalWatchMin / 60)}h ${totalWatchMin % 60}m`
    : `${totalWatchMin}m`;

  const totalQuestions = historyData.sessions?.reduce((acc, curr) => acc + (curr.follow_up_count || 0), 0) || 0;
  const sessionsThisWeek = getSessionsThisWeek(historyData.sessions);
  const activeStreak = computeActiveStreak(analyticsData.daily_activity);
  const weeklyActivity = analyticsData.weekly_contributions || [0, 0, 0, 0, 0, 0, 0];
  const minutesToday = analyticsData.daily_activity?.find(d => d.date === new Date().toISOString().split('T')[0])?.minutes || 0;
  const streakPercent = Math.min((minutesToday / 30) * 100, 100);

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      
      {/* Center Main Dashboard Flow Scroll area */}
      <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: 'var(--space-8)' }}>
        
        {/* Header Greeting */}
        <div style={{ marginBottom: 'var(--space-8)' }}>
          <h1 className="serif-title" style={{ fontSize: '38px', fontWeight: '400', color: 'var(--text-primary)' }}>
            {greeting}, {profile.name || 'Learner'}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            {sessionsThisWeek > 0
              ? `You have generated ${sessionsThisWeek} custom educational video${sessionsThisWeek === 1 ? '' : 's'} this week. Ready to learn more?`
              : historyData.sessions?.length > 0
                ? "Welcome back. Pick a topic below or continue a recent lesson."
                : "Welcome to your adaptive workspace. Ask about any high school textbook topic below."
            }
          </p>
        </div>

        {/* Stats metrics row grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
          <MetricCard
            title="Topics Explored"
            value={analyticsData.topics_covered?.length || 0}
            label="Total syllabus nodes"
            icon="🎓"
            color="var(--text-primary)"
          />
          <MetricCard
            title="Watch Time"
            value={totalWatchTimeText}
            label="Rendered run duration"
            icon="⏱️"
            color="var(--accent-amber)"
          />
          <MetricCard
            title="Current Streak"
            value={`${activeStreak} days`}
            label="Daily targets met"
            icon="🔥"
            color="var(--accent-teal)"
          />
          <MetricCard
            title="Questions Asked"
            value={totalQuestions}
            label="Follow-up chats"
            icon="💬"
            color="var(--accent-violet)"
          />
        </div>

        {/* Continue Learning horizontal timeline strip */}
        {historyData.sessions?.length > 0 && (
          <div style={{ marginBottom: 'var(--space-8)' }}>
            <h3 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
              Continue Studying
            </h3>
            <div style={{ display: 'flex', gap: 'var(--space-4)', overflowX: 'auto', paddingBottom: '10px' }}>
              {historyData.sessions.slice(0, 3).map(sessionItem => (
                <div
                  key={sessionItem.session_id}
                  className="learnos-card"
                  style={{
                    minWidth: '280px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 'var(--space-4)',
                    background: 'var(--bg-surface)'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <SubjectPill subject={sessionItem.subject} />
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {formatSessionDate(sessionItem)}
                      </span>
                    </div>
                    <h4 className="serif-title" style={{ fontSize: '18px', fontWeight: '400', lineHeight: '1.3', color: 'var(--text-primary)' }}>
                      {sessionItem.topic}
                    </h4>
                  </div>
                  <button
                    onClick={() => handleContinueClick(sessionItem.session_id)}
                    className="btn btn-ghost"
                    style={{ alignSelf: 'flex-start', padding: '6px 12px', fontSize: '12px' }}
                  >
                    Load Workspace →
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Adaptive Topic Suggestions Grid list */}
        <div>
          <h3 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
            Suggested Curriculum Topics (Adaptive)
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
            {sortedSuggestions.slice(0, 6).map(suggestion => (
              <div
                key={suggestion.id}
                className="learnos-card interactive"
                onClick={() => handleSuggestionClick(suggestion.title, suggestion.subject)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 'var(--space-3)'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <SubjectPill subject={suggestion.subject} />
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: suggestion.difficulty_color }} />
                      <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{suggestion.difficulty}</span>
                    </div>
                  </div>
                  <h4 className="serif-title" style={{ fontSize: '19px', fontWeight: '400', color: 'var(--text-primary)' }}>
                    {suggestion.title}
                  </h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', marginTop: '6px' }}>
                    {suggestion.summary}
                  </p>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <span>Req: {suggestion.prerequisite}</span>
                  <span className="mono-text" style={{ color: 'var(--accent-amber)' }}>{suggestion.duration} render</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Sidebar Progress Goal Ring Panel */}
      <div
        style={{
          width: '280px',
          height: '100%',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border-subtle)',
          padding: 'var(--space-6)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-8)',
          overflowY: 'auto',
          flexShrink: 0
        }}
      >
        {/* Daily Study target ring */}
        <div>
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
            Today's Target
          </h3>
          <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '140px' }}>
            <svg width="120" height="120" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="50" fill="transparent" stroke="var(--bg-overlay)" strokeWidth="8" />
              <circle
                cx="60"
                cy="60"
                r="50"
                fill="transparent"
                stroke="var(--accent-amber)"
                strokeWidth="8"
                strokeDasharray="314"
                strokeDashoffset={314 - (314 * streakPercent) / 100}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
                style={{ transition: 'stroke-dashoffset 0.8s ease' }}
              />
            </svg>
            <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span className="mono-text" style={{ fontSize: '26px', fontWeight: '500', color: 'var(--accent-amber)', lineHeight: '1' }}>
                {minutesToday}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>/ 30 min</span>
            </div>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', textAlign: 'center', padding: '0 10px', marginTop: '10px' }}>
            {minutesToday >= 30 ? "Daily goal met! Keep going." : `${30 - minutesToday} more minutes to secure today's flame!`}
          </p>
        </div>

        {/* Heatmap Activity Block */}
        <div>
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
            Weekly Activity
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px', background: 'var(--bg-overlay)', padding: '10px', borderRadius: 'var(--r-md)' }}>
            {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => {
              const hasActivity = weeklyActivity[idx] > 0;
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{day}</span>
                  <div
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '4px',
                      background: hasActivity ? 'var(--accent-teal)' : 'var(--bg-raised)',
                      border: hasActivity ? 'none' : '1px solid var(--border-subtle)',
                      transition: 'all 0.3s'
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Recommended Subject Shortcuts */}
        <div>
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
            Quick Refreshers
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <button onClick={() => handleSuggestionClick('Atomic Structure', 'Chemistry')} className="btn btn-ghost" style={{ justifyContent: 'space-between', padding: '8px 12px', fontSize: '12px' }}>
              <span>Atomic Structure</span>
              <span>🧪</span>
            </button>
            <button onClick={() => handleSuggestionClick('Kinematics', 'Physics')} className="btn btn-ghost" style={{ justifyContent: 'space-between', padding: '8px 12px', fontSize: '12px' }}>
              <span>Kinematics Intro</span>
              <span>⚡</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
