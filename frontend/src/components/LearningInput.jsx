import { useState } from 'react';

export default function LearningInput({ onReady, onGenerate, disabled }) {
  const [mode, setMode] = useState('topic');
  const [topic, setTopic] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [prepared, setPrepared] = useState(null);
  const [allowGenerated, setAllowGenerated] = useState(true);
  async function readResponse(response) {
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Unable to prepare learning material');
    return data;
  }
  async function prepare(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      let knowledge;
      if (mode === 'topic' || (mode === 'txt' && text.trim())) {
        const data = await readResponse(await fetch('/api/learning/sessions', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic: topic.trim() || 'My notes', input_mode: mode,
            text: mode === 'txt' ? text : null, allow_generated: allowGenerated })
        }));
        knowledge = data.knowledge;
      } else {
        if (!file) throw new Error('Choose an educational file first.');
        const form = new FormData(); form.append('file', file);
        const material = await readResponse(await fetch('/api/materials/upload', { method: 'POST', body: form }));
        knowledge = await readResponse(await fetch('/api/learning/' + material.session_id));
      }
      setPrepared(knowledge); onReady(knowledge);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div style={{ flex: 1 }}>
    <form onSubmit={prepare} style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      <label>Input <select aria-label="Input mode" value={mode} onChange={e => {
        setMode(e.target.value); setPrepared(null); setFile(null); setError('');
      }} disabled={busy || disabled}>
        <option value="topic">Topic</option><option value="pdf">PDF</option>
        <option value="image">Photo / handwriting</option><option value="txt">TXT</option>
      </select></label>
      {(mode === 'topic' || mode === 'txt') && <input aria-label="Learning topic" value={topic}
        onChange={e => { setTopic(e.target.value); setPrepared(null); }} placeholder="Newton's Laws of Motion"
        required={mode === 'topic'} maxLength={500} style={{ flex: 1, minWidth: 220 }} />}
      {mode !== 'topic' && <input aria-label="Learning material" type="file"
        accept={mode === 'pdf' ? '.pdf' : mode === 'txt' ? '.txt' : '.png,.jpg,.jpeg,.webp'}
        onChange={e => { setFile(e.target.files[0]); setPrepared(null); }} />}
      {mode === 'txt' && <textarea aria-label="Paste educational text" value={text}
        onChange={e => { setText(e.target.value); setPrepared(null); }}
        placeholder="Or paste educational notes" style={{ width: '100%', minHeight: 70 }} />}
      {mode === 'topic' && <label style={{ fontSize: 12 }}>
        <input type="checkbox" checked={allowGenerated} onChange={e => setAllowGenerated(e.target.checked)} />
        Allow labeled AI knowledge if public evidence is unavailable
      </label>}
      <button className="btn btn-secondary" disabled={busy || disabled}>{busy ? 'Understanding content…' : 'Prepare knowledge'}</button>
      <button className="btn btn-primary" type="button" disabled={!prepared || busy || disabled}
        onClick={() => onGenerate(prepared)}>Generate visual lesson</button>
    </form>
    {error && <p role="alert" style={{ color: '#ff9b9b' }}>{error}</p>}
    {prepared && <div style={{ fontSize: 12, marginTop: 10 }}>
      <strong>{prepared.sources.some(s => s.externally_grounded) ? 'SOURCE-BACKED LESSON' : 'AI-GENERATED LESSON KNOWLEDGE'}</strong>
      <p>{prepared.source_chunks.length} evidence chunks · {prepared.concepts.length} extracted concepts · Tutor ready</p>
      {prepared.materials.flatMap(m => m.warnings || []).map((warning, i) => <p key={i} role="status">{warning}</p>)}
      <details><summary>Review extraction and concepts</summary>
        <p>{prepared.concepts.slice(0, 8).map(c => c.name).join(' · ')}</p>
        <p style={{ whiteSpace: 'pre-wrap' }}>{prepared.source_chunks[0]?.text.slice(0, 1800)}</p>
      </details>
    </div>}
  </div>;
}
