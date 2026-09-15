import { useState, useEffect } from 'react';

export default function MarkdownEditor({ notes = '', onNotesChange }) {
  const [localNotes, setLocalNotes] = useState(notes);
  const [syncState, setSyncState] = useState('saved'); // 'saved' | 'saving' | 'idle'

  // Update local notes if prop changes from external load
  useEffect(() => {
    setLocalNotes(notes);
    setSyncState('saved');
  }, [notes]);

  const handleChange = (e) => {
    const val = e.target.value;
    setLocalNotes(val);
    setSyncState('saving');
    onNotesChange(val);
  };

  // Turn saving back to saved after debounced sync timer fires (simulated UI state matching context 3s debounce)
  useEffect(() => {
    if (syncState === 'saving') {
      const t = setTimeout(() => {
        setSyncState('saved');
      }, 3100);
      return () => clearTimeout(t);
    }
  }, [syncState]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden'
      }}
    >
      {/* Editor Header */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-overlay)'
        }}
      >
        <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-primary)' }}>Personal Learning Notebook</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: syncState === 'saved' ? 'var(--accent-teal)' : 'var(--accent-amber)',
              boxShadow: syncState === 'saved' ? '0 0 6px var(--accent-teal)' : '0 0 6px var(--accent-amber)',
              transition: 'background 0.3s'
            }}
          />
          <span className="mono-text" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            {syncState === 'saved' ? 'Synced to server' : 'Saving...'}
          </span>
        </div>
      </div>

      {/* Textarea Input */}
      <textarea
        value={localNotes}
        onChange={handleChange}
        placeholder="# Notes on this lesson&#10;&#10;## Key Concept Insights&#10;Type your summary or equations here...&#10;&#10;## Analogies Explored&#10;* Visual curves mapped..."
        style={{
          flex: 1,
          width: '100%',
          background: 'var(--bg-surface)',
          border: 'none',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)',
          fontSize: '13px',
          lineHeight: '1.6',
          padding: 'var(--space-4)',
          resize: 'none',
          outline: 'none'
        }}
      />
    </div>
  );
}
