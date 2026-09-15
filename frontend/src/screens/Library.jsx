import { useEffect, useState } from 'react';
import SubjectPill from '../components/SubjectPill';
import { useSession } from '../context/SessionContext';
import { getSessionDate, formatSessionDate } from '../utils/sessionHelpers';

export default function Library({ setActiveScreen }) {
  const { loadSessionById } = useSession();
  const [historyData, setHistoryData] = useState({ sessions: [] });
  const [filteredSessions, setFilteredSessions] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');

  // Load history
  useEffect(() => {
    async function fetchHistory() {
      try {
        const response = await fetch('/api/load/history.json');
        if (response.ok) {
          const data = await response.json();
          setHistoryData(data);
          setFilteredSessions(data.sessions || []);
        }
      } catch (err) {
        console.warn('Failed to load library catalog:', err);
      }
    }
    fetchHistory();
  }, []);

  // Filter & Sort
  useEffect(() => {
    if (!historyData.sessions) return;

    let result = [...historyData.sessions];

    // Search query filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(s => s.topic.toLowerCase().includes(query));
    }

    // Subject filter
    if (selectedSubject !== 'All') {
      result = result.filter(s => s.subject === selectedSubject);
    }

    // Sort
    if (sortBy === 'newest') {
      result.sort((a, b) => new Date(getSessionDate(b)) - new Date(getSessionDate(a)));
    } else if (sortBy === 'oldest') {
      result.sort((a, b) => new Date(getSessionDate(a)) - new Date(getSessionDate(b)));
    } else if (sortBy === 'duration') {
      result.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
    }

    setFilteredSessions(result);
  }, [searchQuery, selectedSubject, sortBy, historyData]);

  const handlePlayVideo = async (sid) => {
    setActiveScreen('workspace');
    await loadSessionById(sid);
  };

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: 'var(--space-8)' }}>
      
      {/* Page Title & Search Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
        <div>
          <h1 className="serif-title" style={{ fontSize: '38px', fontWeight: '400', color: 'var(--text-primary)' }}>
            Video Library
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Browse and replay all of your custom-rendered textbook animations.
          </p>
        </div>

        {/* Client side Search */}
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search saved modules..."
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-md)',
            padding: '10px var(--space-4)',
            color: 'var(--text-primary)',
            fontSize: '13px',
            outline: 'none',
            minWidth: '260px'
          }}
        />
      </div>

      {/* Filters & Sorting Tabs Strip */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: 'var(--space-4)',
          marginBottom: 'var(--space-6)',
          flexWrap: 'wrap',
          gap: 'var(--space-3)'
        }}
      >
        {/* Subject Filter Pills */}
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {['All', 'Physics', 'Chemistry', 'Mathematics', 'Biology'].map(subj => (
            <button
              key={subj}
              onClick={() => setSelectedSubject(subj)}
              style={{
                padding: '6px 14px',
                borderRadius: '100px',
                border: 'none',
                background: selectedSubject === subj ? 'var(--accent-amber-dim)' : 'var(--bg-surface)',
                color: selectedSubject === subj ? 'var(--accent-amber)' : 'var(--text-secondary)',
                fontSize: '12px',
                cursor: 'pointer',
                fontWeight: selectedSubject === subj ? '600' : '400',
                transition: 'all 0.2s'
              }}
            >
              {subj}
            </button>
          ))}
        </div>

        {/* Sorting Dropdown selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-primary)',
              borderRadius: 'var(--r-sm)',
              padding: '4px var(--space-2)',
              fontSize: '12px',
              outline: 'none'
            }}
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="duration">Render Length</option>
          </select>
        </div>
      </div>

      {/* Grid List view */}
      {filteredSessions.length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '340px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            gap: 'var(--space-4)'
          }}
        >
          <span style={{ fontSize: '56px' }}>🎬</span>
          <h3 className="serif-title" style={{ fontSize: '22px', color: 'var(--text-primary)', margin: 0 }}>
            Library is Empty
          </h3>
          <p style={{ maxWidth: '300px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            {historyData.sessions?.length === 0
              ? "You haven't generated any lessons yet. Head to the workspace to create your first animated tutorial!"
              : "No saved modules match your active filter settings."}
          </p>
          <button onClick={() => setActiveScreen('workspace')} className="btn btn-primary" style={{ padding: '8px 18px', fontSize: '13px' }}>
            Learn Something Now →
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-6)' }}>
          {filteredSessions.map((sessionItem) => {
            const min = Math.floor((sessionItem.duration_seconds || 30) / 60);
            const sec = Math.floor((sessionItem.duration_seconds || 30) % 60);
            
            return (
              <div
                key={sessionItem.session_id}
                className="learnos-card"
                style={{
                  background: 'var(--bg-surface)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-4)',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {/* Simulated Thumbnail */}
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '16/9',
                    background: 'linear-gradient(135deg, #1f1f2e, #13131a)',
                    borderRadius: 'var(--r-md)',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    position: 'relative'
                  }}
                >
                  <span style={{ fontSize: '32px' }}>🎞️</span>
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '8px',
                      right: '8px',
                      background: 'rgba(0, 0, 0, 0.75)',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      color: '#ffffff',
                      fontFamily: 'var(--font-mono)'
                    }}
                  >
                    {min}:{(sec < 10 ? '0' : '') + sec}
                  </div>
                </div>

                {/* Info Text */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <SubjectPill subject={sessionItem.subject} />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {formatSessionDate(sessionItem)}
                    </span>
                  </div>
                  
                  <h4 className="serif-title" style={{ fontSize: '19px', fontWeight: '400', lineHeight: '1.3', color: 'var(--text-primary)', margin: 0 }}>
                    {sessionItem.topic}
                  </h4>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderTop: '1px solid var(--border-subtle)',
                    paddingTop: 'var(--space-3)',
                    marginTop: 'auto'
                  }}
                >
                  <button
                    onClick={() => handlePlayVideo(sessionItem.session_id)}
                    className="btn btn-primary"
                    style={{ padding: '6px 12px', fontSize: '12px', width: '100%' }}
                  >
                    Replay Module
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
