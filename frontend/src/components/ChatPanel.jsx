import { useState, useEffect, useRef } from 'react';

// Lightweight markdown-to-HTML parser that supports headings, bold, italic, lists, and code blocks safely
function formatMessageContent(text) {
  if (!text) return '';
  
  // Escape HTML characters
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks: ```python ... ```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block"><div class="code-header">${lang || 'code'}</div><code>${code.trim()}</code></pre>`;
  });

  // Inline code: `code`
  html = html.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');

  // Bold: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic: *text*
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Bullet points: - item
  html = html.replace(/^-\s+(.+)$/gm, '<li>$1</li>');
  // Wrap list items in <ul>. A simplistic approach replacing groups of <li>
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Headings: ### title
  html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');

  // Newlines to line breaks (outside pre blocks)
  // Split by code blocks to avoid messing up pre formats
  const parts = html.split(/(<pre[\s\S]*?<\/pre>)/);
  const formattedParts = parts.map(part => {
    if (part.startsWith('<pre')) return part;
    return part.replace(/\n/g, '<br />');
  });

  return <div dangerouslySetInnerHTML={{ __html: formattedParts.join('') }} />;
}

export default function ChatPanel({ messages = [], onSendMessage, isPipelineRunning = false }) {
  const [input, setInput] = useState('');
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isPipelineRunning) return;
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-subtle)'
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          padding: 'var(--space-4) var(--space-5)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)' }}>Co-Pilot Classroom</span>
          <span
            className="mono-text"
            style={{
              fontSize: '10px',
              background: 'rgba(245, 158, 11, 0.08)',
              color: 'var(--accent-amber)',
              padding: '2px 6px',
              borderRadius: '4px',
              border: '1px solid var(--accent-amber-dim)'
            }}
          >
            Gemini Flash
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div
        className="custom-scrollbar"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 'var(--space-5)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)'
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              textAlign: 'center',
              color: 'var(--text-muted)',
              padding: '0 var(--space-4)',
              gap: 'var(--space-2)'
            }}
          >
            <span style={{ fontSize: '28px' }}>🤖</span>
            <p style={{ fontSize: '13px', maxWidth: '240px', lineHeight: '1.5' }}>
              Your classroom co-pilot is ready. Generate a lesson, and ask any follow-up doubts here.
            </p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const isSystem = msg.role === 'system';

            if (isSystem) {
              return (
                <div
                  key={index}
                  style={{
                    alignSelf: 'center',
                    padding: '6px 14px',
                    borderRadius: '100px',
                    background: 'var(--bg-overlay)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    fontSize: '11px',
                    fontStyle: 'italic',
                    margin: 'var(--space-2) 0',
                    maxWidth: '85%',
                    textAlign: 'center'
                  }}
                >
                  {msg.content}
                </div>
              );
            }

            return (
              <div
                key={index}
                style={{
                  alignSelf: isUser ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  alignItems: isUser ? 'flex-end' : 'flex-start'
                }}
              >
                {/* Avatar / Sender Indicator */}
                {!isUser && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                    <span style={{ fontSize: '11px', fontWeight: '500', color: 'var(--text-primary)' }}>LearnOS Agent</span>
                    <span
                      style={{
                        fontSize: '9px',
                        background: 'var(--accent-amber-dim)',
                        color: 'var(--accent-amber)',
                        padding: '1px 4px',
                        borderRadius: '3px',
                        fontWeight: 'bold',
                        letterSpacing: '0.04em'
                      }}
                    >
                      AI
                    </span>
                  </div>
                )}

                {/* Message Bubble */}
                <div
                  className="chat-bubble"
                  style={{
                    background: isUser ? 'var(--accent-blue-dim)' : 'var(--bg-overlay)',
                    border: isUser ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                    borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                    padding: 'var(--space-3) var(--space-4)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                  }}
                >
                  {formatMessageContent(msg.content)}
                  {(msg.sources || []).map((source, index) => <details key={source.chunk_id || index}
                    style={{ marginTop: 8, padding: 8, border: '1px solid var(--border-default)' }}>
                    <summary>{source.title || source.document_id || 'Source'} · {source.source_type || 'curriculum'}</summary>
                    {(source.page || source.pages?.length) && <p>Page: {source.page || source.pages.join(', ')}</p>}
                    {source.section && <p>{source.section}</p>}
                    <p>{source.text || source.excerpt}</p>
                    {source.url?.startsWith('https://en.wikipedia.org/') && <a href={source.url} target="_blank" rel="noreferrer">Open source</a>}
                    <small>{source.trust_label}</small>
                  </details>)}
                </div>

                {/* Timestamp */}
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
              </div>
            );
          })
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Submit form */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: 'var(--space-4)',
          borderTop: '1px solid var(--border-subtle)',
          background: 'var(--bg-surface)'
        }}
      >
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isPipelineRunning ? 'Rendering in progress...' : 'Ask follow-up questions...'}
            disabled={isPipelineRunning}
            style={{
              flex: 1,
              background: 'var(--bg-raised)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-md)',
              padding: '10px var(--space-4)',
              color: 'var(--text-primary)',
              fontSize: '13px',
              outline: 'none',
              transition: 'border-color 0.2s'
            }}
            onFocus={(e) => (e.target.style.borderColor = 'var(--accent-blue)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--border-default)')}
          />
          <button
            type="submit"
            disabled={!input.trim() || isPipelineRunning}
            className="btn btn-primary"
            style={{
              padding: '0 var(--space-5)',
              fontSize: '13px',
              borderRadius: 'var(--r-md)',
              whiteSpace: 'nowrap'
            }}
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
