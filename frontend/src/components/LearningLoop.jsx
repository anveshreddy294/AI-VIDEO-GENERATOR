import { useState } from 'react';

export default function LearningLoop({ session, onVisual }) {
  const [tab, setTab] = useState('Assessment');
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [plan, setPlan] = useState(null);
  const [remediation, setRemediation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function request(url, body) {
    const response = await fetch(url, body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Request failed');
    return data;
  }
  async function act(callback) {
    setBusy(true); setError('');
    try { await callback(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  function loadAssessment() {
    return act(async () => {
      const data = session.assessment_id ? await request('/api/assessment/' + session.assessment_id)
        : await request('/api/assessment/generate', { session_id: session.session_id });
      setAssessment(data); setAnswers({});
    });
  }
  function submit() {
    return act(async () => {
      const data = await request('/api/assessment/' + assessment.assessment_id + '/submit', { answers });
      setResult(data); setPlan(data.roadmap); setTab('Results');
    });
  }
  function relearn(item, mode) {
    return act(async () => {
      const data = await request('/api/learning/' + session.session_id + '/relearn', { concept_id: item.concept_id, mode });
      if (data.assessment) { setAssessment(data.assessment); setAnswers({}); setTab('Assessment'); }
      else if (data.pipeline_request) onVisual(data.pipeline_request);
      else setRemediation(data);
    });
  }
  return <section style={{ padding: 16, border: '1px solid var(--border-default)', borderRadius: 8 }}>
    <nav style={{ display: 'flex', gap: 8 }}>{['Assessment', 'Results', 'Roadmap'].map(name =>
      <button className="btn btn-ghost" key={name} onClick={() => {
        setTab(name);
        if (name === 'Roadmap' && !plan) act(async () => setPlan(await request('/api/roadmap/' + session.session_id)));
      }}>{name}</button>)}</nav>
    {error && <p role="alert" style={{ color: '#ff9b9b' }}>{error}</p>}
    {tab === 'Assessment' && <>
      {!assessment && <button className="btn btn-secondary" onClick={loadAssessment}
        disabled={busy || session.pipeline_stage !== 'complete'}>Start evidence-based assessment</button>}
      {session.pipeline_stage !== 'complete' && <p>Assessment unlocks after a playable video is completed.</p>}
      {assessment && <div>
        <p>Source-based recall questions</p>
        {assessment.questions.map((q, i) => <fieldset key={q.question_id} style={{ marginBottom: 12 }}>
          <legend>{i + 1}. {q.question}</legend>
          {q.type === 'mcq' ? q.options.map(option => <label key={option} style={{ display: 'block', margin: 6 }}>
            <input type="radio" name={q.question_id} checked={answers[q.question_id] === option}
              onChange={() => setAnswers(prev => ({ ...prev, [q.question_id]: option }))} /> {option}
          </label>) : <textarea aria-label="Descriptive answer" value={answers[q.question_id] || ''}
            onChange={e => setAnswers(prev => ({ ...prev, [q.question_id]: e.target.value }))} maxLength={5000} />}
        </fieldset>)}
        <button className="btn btn-primary" disabled={busy} onClick={submit}>Submit assessment</button>
      </div>}
    </>}
    {tab === 'Results' && (result ? <div>
      <h3>Overall score: {result.score}%</h3>
      {result.concept_scores.map(c => <p key={c.concept_id}>
        {session.knowledge?.concepts.find(x => x.concept_id === c.concept_id)?.name || 'Assessed concept'}:
        {' '}{c.score}% · {c.status.replaceAll('_', ' ')}</p>)}
      {result.feedback.map(f => <details key={f.question_id}><summary>{f.feedback} · {f.score}%</summary>
        <p>{f.explanation}</p>{f.missing_points?.length > 0 && <p>Missing rubric terms: {f.missing_points.join(', ')}</p>}
      </details>)}
      <p>Descriptive responses use a keyword rubric; reasoning quality needs teacher review.</p>
    </div> : <p>Complete an assessment to see results.</p>)}
    {tab === 'Roadmap' && (plan ? <ol>{plan.items.map(item => <li key={item.roadmap_item_id} style={{ marginBottom: 14 }}>
      <strong>{item.title}</strong><p>{item.reason} About {item.estimated_minutes} minutes.</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {[['simple_explanation', 'Teach more simply'], ['real_world_analogy', 'Analogy'],
          ['worked_example', 'Worked example'], ['targeted_visual', 'Mini visual lesson'], ['mini_retest', '3-question retest']]
          .map(([mode, label]) => <button key={mode} disabled={busy} onClick={() => relearn(item, mode)}>{label}</button>)}
      </div>
    </li>)}</ol> : <p>A roadmap requires actual assessment results.</p>)}
    {remediation && <div style={{ whiteSpace: 'pre-wrap' }}><p>{remediation.answer}</p>
      {remediation.fallback_used && <small>Provider unavailable: retrieved evidence is shown.</small>}</div>}
    {session.provenance && <details><summary>Lesson diagnostics: {session.provenance.outcome}</summary>
      <p>{session.provenance.retrieval_mode} · {session.provenance.scenes?.length} scenes</p>
      {session.provenance.scenes?.map(scene => <p key={scene.scene_id}>Scene {scene.scene_id}: {scene.compile_status},
        {' '}{scene.render_status}, {scene.tts_provider}{scene.render_fallback_used ? ' (fallback)' : ''}</p>)}
    </details>}
  </section>;
}
