import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { lessonApi } from '../../services/api/lessonApi';
import { videoApi } from '../../services/api/videoApi';
import { toUserMessage } from '../../services/api/errors';
import { useAnimatedCounter, useDiagramAnimation, animateTapFeedback } from '../../animations';
import {
  GlyphArrowRight,
  GlyphCheckmark,
  GlyphDocument,
  GlyphEvidence,
  GlyphPlay,
  GlyphRotate
} from '../../components/ui/AtelierGlyphs';

const TAB_DEFINITIONS = [
  { id: 'learn', label: 'Learn', description: 'Explanation and examples' },
  { id: 'notes', label: 'Notes', description: 'Concise study notes' },
  { id: 'visualize', label: 'Visualize', description: 'Concept relationships' },
  { id: 'practice', label: 'Practice', description: 'Server-graded questions' },
  { id: 'ask', label: 'Ask AI', description: 'Ask about this lesson' },
  { id: 'video', label: 'Video', description: 'Narrated explanation' }
];
const ACTIVE_VIDEO_STATUSES = new Set(['QUEUED', 'PLANNING', 'GENERATING_AUDIO', 'ALIGNING', 'RENDERING', 'COMPOSITING']);

function ErrorNotice({ error }) {
  return error ? <div className="workspace-error-notice" role="alert"><strong>Something needs attention</strong><span>{toUserMessage(error)}</span></div> : null;
}

function SectionIntro({ eyebrow, title, description, action }) {
  return <div className="workspace-section-intro"><div><span className="coord-label">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>{action}</div>;
}

function LearnPanel({ lesson, onTabChange }) {
  const content = lesson.content;
  const concepts = content.key_concepts || [];
  const examples = content.examples || [];
  const equations = content.equations || [];
  const observations = content.source_observations || [];
  return <section className="workspace-panel" aria-labelledby="learn-panel-heading"><SectionIntro eyebrow="LEARN · START HERE" title="Understand the lesson" description="Read the explanation first, then use the other views when you want to go deeper." action={<span className="workspace-status-chip">{content.status || 'READY'}</span>} /><div className="workspace-explanation-card"><p className="workspace-explanation">{content.explanation}</p></div>{concepts.length > 0 && <div className="workspace-content-block"><h3 id="learn-panel-heading">Key concepts</h3><div className="workspace-concept-grid">{concepts.map(concept => <article className="workspace-concept-card" key={concept.name}><span className="concept-index">CONCEPT</span><h4>{concept.name}</h4><p>{concept.explanation}</p></article>)}</div></div>}{examples.length > 0 && <div className="workspace-content-block"><h3>Examples</h3><ul className="workspace-example-list">{examples.map((example, index) => <li key={`${example}-${index}`}>{example}</li>)}</ul></div>}{equations.length > 0 && <div className="workspace-content-block"><h3>Equations and notation</h3><div className="workspace-equation-list">{equations.map((equation, index) => <pre key={`${equation}-${index}`}>{equation}</pre>)}</div></div>}{observations.length > 0 && <div className="workspace-evidence-note"><GlyphEvidence size={14} /><span>This lesson includes {observations.length} returned source observation{observations.length === 1 ? '' : 's'}.</span></div>}<div className="workspace-next-step"><div><span className="coord-label">A USEFUL NEXT STEP</span><strong>Turn the explanation into a shorter revision guide.</strong><p>Notes are optional and can be generated when you are ready.</p></div><button type="button" className="btn-atelier-outline" onClick={() => onTabChange('notes')}>Open Notes <GlyphArrowRight size={12} /></button></div></section>;
}

function NotesPanel({ lesson, loadLesson }) {
  const [notes, setNotes] = useState(lesson.notes || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => { setNotes(lesson.notes || null); }, [lesson.id, lesson.notes]);
  const generate = async () => {
    setBusy(true); setError(null);
    try { const result = await lessonApi.notes(lesson.id, { detail_level: 'standard', regenerate: Boolean(notes) }); setNotes(result); await loadLesson(lesson.id); } catch (requestError) { setError(requestError); } finally { setBusy(false); }
  };
  return <section className="workspace-panel" aria-labelledby="notes-panel-heading"><SectionIntro eyebrow="NOTES" title="Build a revision guide" description="Generate concise notes from this lesson when you are ready. Opening this tab never starts a generation request." action={<button type="button" className="btn-atelier-primary" disabled={busy} onClick={generate}>{busy ? 'Generating notes…' : notes ? 'Regenerate Notes' : 'Generate Notes'} <GlyphDocument size={12} /></button>} /><ErrorNotice error={error} />{notes ? <div className="workspace-notes-sheet"><span className="coord-label">{notes.detail_level?.toUpperCase() || 'STANDARD'} STUDY NOTES</span><h3 id="notes-panel-heading">{notes.title}</h3><p className="workspace-notes-summary">{notes.summary}</p>{(notes.key_points || []).length > 0 && <div className="workspace-notes-section"><h4>Key points</h4>{notes.key_points.map((point, index) => <div className="workspace-note-row" key={`${point}-${index}`}><span>•</span><p>{point}</p></div>)}</div>}{(notes.key_concepts || []).length > 0 && <div className="workspace-notes-section"><h4>Concepts to remember</h4>{notes.key_concepts.map(note => <div className="workspace-note-row" key={note.name}><span>•</span><p><strong>{note.name}: </strong>{note.explanation}</p></div>)}</div>}{(notes.examples || []).length > 0 && <div className="workspace-notes-section"><h4>Examples</h4>{notes.examples.map((example, index) => <div className="workspace-note-row" key={`${example}-${index}`}><span>•</span><p>{example}</p></div>)}</div>}</div> : <div className="workspace-empty-panel"><GlyphDocument size={24} /><h3 id="notes-panel-heading">Notes have not been generated</h3><p>When you want a revision guide, choose Generate Notes. Your lesson stays available while it is prepared.</p><button type="button" className="btn-atelier-primary" disabled={busy} onClick={generate}>Generate Notes <GlyphArrowRight size={12} /></button></div>}</section>;
}

function VisualizePanel({ lesson, loadLesson, onTabChange }) {
  const [diagram, setDiagram] = useState(lesson.diagram || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const diagramRef = useRef(null);

  useEffect(() => { setDiagram(lesson.diagram || null); }, [lesson.id, lesson.diagram]);
  useDiagramAnimation(diagramRef, [diagram]);

  const validEdges = useMemo(() => {
    if (!diagram) return [];
    const nodeIds = new Set((diagram.nodes || []).map(node => node.node_id));
    return (diagram.edges || []).filter(edge => nodeIds.has(edge.from_node) && nodeIds.has(edge.to_node));
  }, [diagram]);

  const generate = async () => {
    setBusy(true); setError(null);
    try { const result = await lessonApi.diagram(lesson.id, { regenerate: Boolean(diagram) }); setDiagram(result); await loadLesson(lesson.id); } catch (requestError) { setError(requestError); } finally { setBusy(false); }
  };

  return (
    <section className="workspace-panel" aria-labelledby="visualize-panel-heading">
      <SectionIntro 
        eyebrow="VISUALIZE" 
        title="See how the ideas connect" 
        description="The flowchart below is returned by the backend for this lesson. Generate it only when you want a visual view." 
        action={
          <button type="button" className="btn-atelier-primary" disabled={busy} onClick={generate}>
            {busy ? 'Generating diagram…' : diagram ? 'Regenerate Flowchart' : 'Generate Flowchart'} <GlyphEvidence size={12} />
          </button>
        } 
      />
      <ErrorNotice error={error} />
      {diagram ? (
        <div className="workspace-diagram-card" ref={diagramRef}>
          <div className="card-top-bar" style={{ marginBottom: '14px' }}>
            <h3 id="visualize-panel-heading">{diagram.title?.text || 'Lesson relationships'}</h3>
            <span className="card-badge-soft">{(diagram.nodes || []).length} NODES · {validEdges.length} EDGES</span>
          </div>
          <div className="workspace-diagram-nodes">
            {(diagram.nodes || []).map((node, index) => {
              const isHovered = hoveredNode === node.node_id;
              return (
                <div 
                  className={`workspace-diagram-node ${isHovered ? 'active-hover' : ''}`} 
                  key={node.node_id}
                  onMouseEnter={() => setHoveredNode(node.node_id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                    borderColor: isHovered ? 'var(--terracotta)' : undefined,
                    transform: isHovered ? 'translateY(-2px)' : undefined
                  }}
                >
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{node.item?.text}</strong>
                </div>
              );
            })}
          </div>
          {validEdges.length > 0 && (
            <div className="workspace-diagram-edges" style={{ marginTop: '18px' }}>
              <span className="coord-label">CONNECTIONS IN THIS LESSON</span>
              {validEdges.map((edge, index) => {
                const isConnected = hoveredNode && (hoveredNode === edge.from_node || hoveredNode === edge.to_node);
                return (
                  <div 
                    className={`workspace-diagram-edge ${isConnected ? 'active-highlight' : ''}`} 
                    key={`${edge.from_node}-${edge.to_node}-${index}`}
                    style={{
                      transition: 'all 0.18s ease',
                      borderColor: isConnected ? 'var(--terracotta)' : undefined,
                      backgroundColor: isConnected ? 'var(--terracotta-subtle)' : undefined
                    }}
                  >
                    <strong>{edge.from_node}</strong>
                    <span style={{ color: isConnected ? 'var(--terracotta)' : undefined }}>→</span>
                    <strong>{edge.to_node}</strong>
                    <small>{edge.item?.text}</small>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="workspace-empty-panel">
          <GlyphEvidence size={24} />
          <h3 id="visualize-panel-heading">No visualization yet</h3>
          <p>Generate a flowchart to explore the relationships returned for this lesson.</p>
          <button type="button" className="btn-atelier-primary" disabled={busy} onClick={generate}>
            Generate Flowchart <GlyphArrowRight size={12} />
          </button>
        </div>
      )}
      <div className="workspace-next-step">
        <div>
          <span className="coord-label">A USEFUL NEXT STEP</span>
          <strong>Test what you understand.</strong>
          <p>Practice uses the assessment engine for this same lesson.</p>
        </div>
        <button type="button" className="btn-atelier-outline" onClick={() => onTabChange('practice')}>
          Open Practice <GlyphArrowRight size={12} />
        </button>
      </div>
    </section>
  );
}

function PracticeResultCard({ result, onReset }) {
  const animatedScore = useAnimatedCounter(result.percentage || 0, 750);
  const isPassed = (result.percentage || 0) >= 70;

  return (
    <div className={`workspace-result-card ${isPassed ? 'passed' : 'review'}`}>
      <div className="workspace-result-header">
        <div>
          <span className="coord-label">SERVER-GRADED ASSESSMENT RESULT</span>
          <div className="workspace-score-display">
            <strong className="workspace-score-number">{animatedScore}%</strong>
            <span className={`workspace-score-badge ${isPassed ? 'passed' : 'review'}`}>
              {isPassed ? '✓ Passed' : 'Needs Review'}
            </span>
          </div>
        </div>
        {result.submitted_at && (
          <span className="coord-label">
            GRADED {new Date(result.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      <p className="workspace-score-feedback">{result.feedback}</p>

      {result.descriptive_feedback && (
        <div className="workspace-descriptive-feedback">
          <span className="coord-label">WRITTEN RESPONSE FEEDBACK</span>
          <p>{result.descriptive_feedback}</p>
        </div>
      )}

      <div style={{ marginTop: '8px' }}>
        <button type="button" className="btn-atelier-outline" onClick={onReset}>
          <GlyphRotate size={12} /> Retake Assessment
        </button>
      </div>
    </div>
  );
}

function PracticePanel({ lesson, loadLesson }) {
  const latestSubmission = Array.isArray(lesson.submissions) && lesson.submissions.length > 0
    ? lesson.submissions[lesson.submissions.length - 1]
    : null;

  const [assessment, setAssessment] = useState(lesson.assessment || null);
  const [answers, setAnswers] = useState(() => {
    if (latestSubmission && Array.isArray(latestSubmission.mcq_results)) {
      const restored = {};
      for (const item of latestSubmission.mcq_results) {
        if (item.chosen_index !== undefined && item.chosen_index !== null) {
          restored[item.question_id] = item.chosen_index;
        }
      }
      return restored;
    }
    return {};
  });
  const [descriptiveAnswer, setDescriptiveAnswer] = useState('');
  const [result, setResult] = useState(latestSubmission || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Synchronize ONLY when lesson identity changes, avoiding state wipe after submission
  useEffect(() => {
    setAssessment(lesson.assessment || null);
    const sub = Array.isArray(lesson.submissions) && lesson.submissions.length > 0
      ? lesson.submissions[lesson.submissions.length - 1]
      : null;
    if (sub) {
      setResult(sub);
      if (Array.isArray(sub.mcq_results)) {
        const restored = {};
        for (const item of sub.mcq_results) {
          if (item.chosen_index !== undefined && item.chosen_index !== null) {
            restored[item.question_id] = item.chosen_index;
          }
        }
        setAnswers(restored);
      }
    } else {
      setResult(null);
      setAnswers({});
      setDescriptiveAnswer('');
    }
  }, [lesson.id]);

  // Handle asynchronous assessment generation on current lesson
  useEffect(() => {
    if (lesson.assessment && !assessment) {
      setAssessment(lesson.assessment);
    }
  }, [lesson.assessment]);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const generated = await lessonApi.assessment(lesson.id);
      setAssessment(generated);
      await loadLesson(lesson.id);
    } catch (requestError) {
      setError(requestError);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setAnswers({});
    setDescriptiveAnswer('');
    setError(null);
  };

  const totalMcqs = assessment?.mcqs?.length || 0;
  const answeredMcqs = assessment?.mcqs?.filter(q => answers[q.question_id] !== undefined).length || 0;
  const hasDescriptive = Boolean(descriptiveAnswer.trim());
  const complete = assessment && (totalMcqs > 0 ? answeredMcqs === totalMcqs : true) && hasDescriptive;

  const submit = async event => {
    event.preventDefault();
    if (!complete) {
      setError(new Error('Please answer all multiple-choice questions and write a brief response before submitting for grading.'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const graded = await lessonApi.submitAssessment(lesson.id, {
        mcq_answers: answers,
        descriptive_answer: descriptiveAnswer
      });
      setResult(graded);
      // Reload parent lesson progress without overwriting active result state
      await loadLesson(lesson.id);
    } catch (requestError) {
      setError(requestError);
    } finally {
      setBusy(false);
    }
  };

  const gradedResults = new Map((result?.mcq_results || []).map(item => [item.question_id, item]));

  return (
    <section className="workspace-panel" aria-labelledby="practice-panel-heading">
      <SectionIntro 
        eyebrow="PRACTICE" 
        title="Check your understanding" 
        description="Questions are generated and graded by the assessment engine for this lesson." 
        action={
          result ? (
            <span 
              className="workspace-status-chip practice-graded-chip"
              style={{
                backgroundColor: result.percentage >= 70 ? 'rgba(51, 86, 68, 0.12)' : 'rgba(164, 96, 71, 0.12)',
                color: result.percentage >= 70 ? 'var(--evergreen)' : 'var(--terracotta)',
                borderColor: result.percentage >= 70 ? 'var(--evergreen)' : 'var(--terracotta)'
              }}
            >
              GRADED · {result.percentage}%
            </span>
          ) : assessment ? (
            <span className="workspace-status-chip">NOT SUBMITTED</span>
          ) : null
        } 
      />
      <ErrorNotice error={error} />
      {!assessment ? (
        <div className="workspace-empty-panel">
          <GlyphCheckmark size={24} />
          <h3 id="practice-panel-heading">Practice is ready when you are</h3>
          <p>Start Practice to request the real question set. Viewing this tab does not generate questions.</p>
          <button type="button" className="btn-atelier-primary" disabled={busy} onClick={generate}>
            {busy ? 'Preparing practice…' : 'Start Practice'} <GlyphArrowRight size={12} />
          </button>
        </div>
      ) : (
        <form className="workspace-practice-form" onSubmit={submit}>
          {result && (
            <PracticeResultCard 
              result={result} 
              onReset={handleReset} 
            />
          )}

          <div className="workspace-assessment-meta">
            <span className="coord-label">ASSESSMENT {assessment.assessment_id}</span>
            <span className="coord-label">{totalMcqs} MULTIPLE-CHOICE · 1 WRITTEN</span>
          </div>

          {assessment.mcqs?.map((question, questionIndex) => {
            const graded = gradedResults.get(question.question_id);
            const isCorrect = graded?.is_correct;
            return (
              <fieldset className="workspace-question" key={question.question_id}>
                <legend>
                  {questionIndex + 1}. {question.prompt}
                  {graded && (
                    <span className={`grade-badge ${isCorrect ? 'correct' : 'incorrect'}`}>
                      {isCorrect ? '✓ Correct' : '✗ Incorrect'}
                    </span>
                  )}
                </legend>
                <div className="workspace-options">
                  {question.options.map((option, index) => {
                    const isSelected = answers[question.question_id] === index;
                    const isGradedCorrect = graded && graded.correct_index === index;
                    const isGradedIncorrect = graded && graded.chosen_index === index && !graded.is_correct;
                    return (
                      <label 
                        className={`workspace-option ${isSelected ? 'selected' : ''} ${isGradedCorrect ? 'correct' : ''} ${isGradedIncorrect ? 'incorrect' : ''}`} 
                        key={option}
                      >
                        <input 
                          type="radio" 
                          name={question.question_id} 
                          disabled={Boolean(result)} 
                          checked={isSelected} 
                          onChange={() => setAnswers(previous => ({ ...previous, [question.question_id]: index }))} 
                        />
                        <span>{String.fromCharCode(65 + index)}</span>
                        <b>{option}</b>
                      </label>
                    );
                  })}
                </div>
                {graded?.explanation && (
                  <div className="workspace-server-feedback">
                    <strong>Explanation:</strong> {graded.explanation}
                  </div>
                )}
              </fieldset>
            );
          })}

          <div className="workspace-question workspace-written-question">
            <label htmlFor="workspace-descriptive-answer">{assessment.descriptive?.prompt}</label>
            <textarea 
              id="workspace-descriptive-answer" 
              className="atelier-input" 
              rows="6" 
              maxLength={12000} 
              value={descriptiveAnswer} 
              disabled={Boolean(result)} 
              onChange={event => setDescriptiveAnswer(event.target.value)} 
              placeholder="Write your answer for server-side grading…" 
              required 
            />
            {result?.descriptive_feedback && (
              <div className="workspace-server-feedback" style={{ borderLeft: '3px solid var(--evergreen)', marginTop: '12px' }}>
                <strong>Server Rubric Evaluation:</strong> {result.descriptive_feedback}
              </div>
            )}
          </div>

          {result ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
              <button type="button" className="btn-atelier-outline" onClick={handleReset}>
                <GlyphRotate size={12} /> Retake Assessment
              </button>
              <span className="coord-label">OFFICIAL SCORE: {result.percentage}% SAVED</span>
            </div>
          ) : (
            <>
              <div className="workspace-submission-checklist">
                <span className="coord-label">SUBMISSION CHECKLIST</span>
                <div className="checklist-items">
                  <span className={`checklist-item ${answeredMcqs === totalMcqs ? 'complete' : 'pending'}`}>
                    {answeredMcqs === totalMcqs ? '✓' : '○'} Multiple Choice: {answeredMcqs}/{totalMcqs} answered
                  </span>
                  <span className={`checklist-item ${hasDescriptive ? 'complete' : 'pending'}`}>
                    {hasDescriptive ? '✓' : '○'} Written Response: {hasDescriptive ? 'Answer provided' : 'Required for grading'}
                  </span>
                </div>
              </div>
              <button 
                type="submit" 
                className="btn-atelier-primary" 
                disabled={busy}
              >
                {busy ? 'Submitting answers…' : 'Submit Answers'} <GlyphCheckmark size={12} />
              </button>
              {!complete && (
                <span className="workspace-submit-hint">
                  Answer all questions and write a response above to submit for server grading.
                </span>
              )}
            </>
          )}
        </form>
      )}
    </section>
  );
}

function AskPanel({ lesson }) {
  const [question, setQuestion] = useState('');
  const [answers, setAnswers] = useState(() => (lesson.ask_history || []).map(item => ({ question: item.question, ...item.answer })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { setAnswers((lesson.ask_history || []).map(item => ({ question: item.question, ...item.answer }))); }, [lesson.id, lesson.ask_history]);

  const ask = async event => {
    event.preventDefault(); if (!question.trim()) return;
    const asked = question.trim(); setBusy(true); setError(null); setQuestion('');
    try { const answer = await lessonApi.ask(lesson.id, asked); setAnswers(previous => [...previous, answer]); } catch (requestError) { setError(requestError); setQuestion(asked); } finally { setBusy(false); }
  };

  return (
    <section className="workspace-panel" aria-labelledby="ask-panel-heading">
      <SectionIntro 
        eyebrow="ASK VISUALAI" 
        title="Ask a question about this lesson" 
        description="VisualAI will answer using the current lesson context and will show the evidence status returned by the backend." 
      />
      <ErrorNotice error={error} />
      <div className="workspace-ask-card">
        <div className="ask-chat-history">
          {answers.length === 0 && (
            <div className="workspace-empty-chat">
              <GlyphEvidence size={22} />
              <p>Ask anything that is confusing, such as “What is the main idea?”</p>
            </div>
          )}
          {answers.map((answer, index) => (
            <article className="workspace-chat-message" key={`${answer.question}-${index}`}>
              <span className="coord-label">{answer.evidence_status || 'BACKEND ANSWER'}</span>
              <strong>{answer.question}</strong>
              <p>{answer.answer}</p>
              {answer.citations?.length > 0 && (
                <small><GlyphEvidence size={11} /> {answer.citations.length} returned citation{answer.citations.length === 1 ? '' : 's'}</small>
              )}
            </article>
          ))}
          {busy && (
            <div className="workspace-chat-message thinking-bubble" style={{ display: 'flex', alignItems: 'center', gap: '8px', opacity: 0.85, padding: '12px' }}>
              <span className="status-live-beacon" />
              <span className="coord-label">VISUALAI IS SYNTHESIZING ANSWER FROM LESSON EVIDENCE…</span>
            </div>
          )}
        </div>
        <form onSubmit={ask} className="workspace-ask-form">
          <label htmlFor="workspace-question">Your question</label>
          <div>
            <input 
              id="workspace-question" 
              className="atelier-text-input" 
              value={question} 
              maxLength={4000} 
              disabled={busy} 
              onChange={event => setQuestion(event.target.value)} 
              placeholder={`Ask about ${lesson.topic}…`} 
            />
            <button type="submit" className="btn-atelier-primary" disabled={busy || !question.trim()}>
              {busy ? 'Asking…' : 'Ask VisualAI'} <GlyphArrowRight size={12} />
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function VideoPanel({ lesson, videoJobStatus, setVideoJobStatus, active }) {
  const [status, setStatus] = useState(lesson.video || null);
  const [mediaUrl, setMediaUrl] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);
  useEffect(() => { setStatus(lesson.video || null); setMediaUrl(null); setError(null); }, [lesson.id]);
  useEffect(() => () => { window.clearTimeout(timerRef.current); if (mediaUrl) URL.revokeObjectURL(mediaUrl); }, [mediaUrl]);
  const loadMedia = async () => {
    try { const blob = await videoApi.stream(lesson.id); setMediaUrl(previous => { if (previous) URL.revokeObjectURL(previous); return URL.createObjectURL(blob); }); } catch (requestError) { setError(requestError); }
  };
  const poll = async () => {
    window.clearTimeout(timerRef.current);
    try { const next = await videoApi.status(lesson.id); setStatus(next); setVideoJobStatus(next); if (next.status === 'COMPLETED') await loadMedia(); if (ACTIVE_VIDEO_STATUSES.has(next.status)) timerRef.current = window.setTimeout(poll, 2500); } catch (requestError) { setError(requestError); }
  };
  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    const inspect = async () => {
      try {
        const next = await videoApi.status(lesson.id);
        if (cancelled) return;
        setStatus(next); setVideoJobStatus(next);
        if (next.status === 'COMPLETED' && !mediaUrl) await loadMedia();
        if (ACTIVE_VIDEO_STATUSES.has(next.status)) timerRef.current = window.setTimeout(inspect, 2500);
      } catch (requestError) { if (!cancelled) setError(requestError); }
    };
    inspect();
    return () => { cancelled = true; window.clearTimeout(timerRef.current); };
  }, [active, lesson.id]);
  const start = async () => {
    if (busy || ACTIVE_VIDEO_STATUSES.has(status?.status)) return;
    setBusy(true); setError(null);
    try { const next = await videoApi.start(lesson.id); setStatus(next); setVideoJobStatus(next); if (next.status === 'COMPLETED') await loadMedia(); else timerRef.current = window.setTimeout(poll, 800); } catch (requestError) { setError(requestError); } finally { setBusy(false); }
  };
  const download = () => { if (!mediaUrl) return; const anchor = document.createElement('a'); anchor.href = mediaUrl; anchor.download = `${lesson.topic.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.mp4`; document.body.appendChild(anchor); anchor.click(); anchor.remove(); };
  const current = status;
  const isCompleted = current?.status === 'COMPLETED' && mediaUrl;
  return <section className="workspace-panel" aria-labelledby="video-panel-heading"><SectionIntro eyebrow="VIDEO" title={isCompleted ? 'Watch your explanation video' : 'Generate an explanation video'} description="Video generation uses the existing renderer. Opening this tab never starts a job automatically." action={current?.status ? <span className="workspace-status-chip">{current.status.replaceAll('_', ' ')}</span> : null} /><ErrorNotice error={error} />{isCompleted ? <div className="workspace-video-card"><video controls preload="metadata" src={mediaUrl} aria-label={`Explanation video for ${lesson.topic}`} /><div className="workspace-video-actions"><span className="coord-label">BACKEND-CONFIRMED MP4 · {current.duration_seconds ? `${current.duration_seconds}s` : 'duration available in player'}</span><button type="button" className="btn-atelier-outline" onClick={download}>Download Video <GlyphArrowRight size={12} /></button></div></div> : <div className="workspace-empty-panel"><GlyphPlay size={24} /><h3 id="video-panel-heading">{ACTIVE_VIDEO_STATUSES.has(current?.status) ? 'Your video is being prepared' : current?.status === 'FAILED' ? 'Video generation failed' : 'Video is optional'}</h3><p>{ACTIVE_VIDEO_STATUSES.has(current?.status) ? `${current.stage || 'The renderer is working'} · ${current.progress ?? 0}%` : current?.status === 'FAILED' ? 'The backend reported a failed video job. You can retry when the service is ready.' : 'Create a narrated explanation when you want another way to review this lesson.'}</p><button type="button" className="btn-atelier-primary" disabled={busy || ACTIVE_VIDEO_STATUSES.has(current?.status)} onClick={start}>{busy ? 'Starting video…' : current?.status === 'FAILED' ? 'Retry Video' : 'Generate Explanation Video'} <GlyphPlay size={12} /></button></div>}</section>;
}

export default function LearningStudioPage() {
  const { activeLesson, activeLessonId, setActiveLessonId, loadLesson, workspaceStatus, workspaceError, videoJobStatus, setVideoJobStatus } = useAtelierWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const search = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const queryLessonId = search.get('lesson');
  const requestedTab = search.get('tab') || 'learn';
  const activeTab = TAB_DEFINITIONS.some(tab => tab.id === requestedTab) ? requestedTab : 'learn';

  useEffect(() => { if (queryLessonId && queryLessonId !== activeLessonId) setActiveLessonId(queryLessonId); }, [queryLessonId, activeLessonId, setActiveLessonId]);
  const updateTab = tab => {
    const params = new URLSearchParams();
    if (activeLesson?.id || activeLessonId) params.set('lesson', activeLesson?.id || activeLessonId);
    params.set('tab', tab);
    navigate(`/app/studio?${params.toString()}`);
  };
  const openLessonList = () => navigate('/app/explore');

  if (!activeLesson) return <div className="workspace-page-root"><section className="atelier-page-header"><div className="header-meta-row"><span className="coord-label">LEARNING WORKSPACE</span></div><h1 className="page-heading">Choose a lesson to begin</h1><p className="page-subheading">Your explanation, notes, visualization, practice, questions and video all live here once you open a saved lesson.</p>{workspaceStatus === 'loading' && <p className="coord-label">Loading your learning context…</p>}{workspaceError && <ErrorNotice error={workspaceError} />}<button type="button" className="btn-atelier-primary" onClick={openLessonList}>Open My Learning <GlyphArrowRight size={12} /></button></section></div>;

  return <div className="workspace-page-root learning-workspace-root"><section className="blueprint-frame learning-workspace-header" style={{ padding: '24px 28px' }}><div className="learning-workspace-header-top"><button type="button" className="workspace-back-link" onClick={openLessonList}>← Back to My Learning</button><span className="coord-label">LESSON {activeLesson.id}</span></div><div className="learning-workspace-title-row"><div><span className="dash-hero-kicker-tag"><GlyphEvidence size={13} /><span>YOUR LEARNING WORKSPACE</span></span><h1 className="page-heading">{activeLesson.topic}</h1><p className="page-subheading">{activeLesson.source_id ? `From your material · ${activeLesson.source_id} · version ${activeLesson.source_version}` : 'Topic lesson · structured by VisualAI'}</p></div><span className="workspace-status-chip">READY TO LEARN</span></div><div className="learning-workspace-tabs" role="tablist" aria-label="Lesson activities">{TAB_DEFINITIONS.map(tab => <button type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`workspace-panel-${tab.id}`} className={`learning-workspace-tab ${activeTab === tab.id ? 'active' : ''}`} key={tab.id} onClick={() => updateTab(tab.id)}><strong>{tab.label}</strong><small>{tab.description}</small></button>)}</div></section><main className="learning-workspace-content"><div id="workspace-panel-learn" role="tabpanel" hidden={activeTab !== 'learn'}><LearnPanel lesson={activeLesson} onTabChange={updateTab} /></div><div id="workspace-panel-notes" role="tabpanel" hidden={activeTab !== 'notes'}><NotesPanel lesson={activeLesson} loadLesson={loadLesson} /></div><div id="workspace-panel-visualize" role="tabpanel" hidden={activeTab !== 'visualize'}><VisualizePanel lesson={activeLesson} loadLesson={loadLesson} onTabChange={updateTab} /></div><div id="workspace-panel-practice" role="tabpanel" hidden={activeTab !== 'practice'}><PracticePanel lesson={activeLesson} loadLesson={loadLesson} /></div><div id="workspace-panel-ask" role="tabpanel" hidden={activeTab !== 'ask'}><AskPanel lesson={activeLesson} /></div><div id="workspace-panel-video" role="tabpanel" hidden={activeTab !== 'video'}><VideoPanel active={activeTab === 'video'} lesson={activeLesson} videoJobStatus={videoJobStatus} setVideoJobStatus={setVideoJobStatus} /></div></main></div>;
}
