import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAtelierWorkspace } from '../../context/WorkspaceContext';
import { 
  GlyphCheckmark, 
  GlyphCrosshair, 
  GlyphArrowRight, 
  GlyphRotate,
  GlyphDocument 
} from '../../components/ui/AtelierGlyphs';

export default function AssessmentPage() {
  const { 
    activeSource, 
    activeConcept, 
    assessmentQuestions, 
    submitAssessmentAnswer, 
    masteryScores 
  } = useAtelierWorkspace();

  const navigate = useNavigate();
  const [questionCount, setQuestionCount] = useState(5);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [correctCount, setCorrectCount] = useState(0);

  // Active question set based on user-chosen count (5, 10, 15, 20)
  const activeQuestions = assessmentQuestions.slice(0, questionCount);
  const question = activeQuestions[currentIdx] || activeQuestions[0];
  const isLastQuestion = currentIdx === activeQuestions.length - 1;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (selectedOption === null) return;

    const result = submitAssessmentAnswer(question.id, selectedOption);
    setLastResult(result);
    setSubmitted(true);
    if (result.isCorrect) {
      setCorrectCount(prev => prev + 1);
    }
  };

  const handleNext = () => {
    if (!isLastQuestion) {
      setCurrentIdx(prev => prev + 1);
      setSelectedOption(null);
      setSubmitted(false);
      setLastResult(null);
    } else {
      navigate('/app/progress');
    }
  };

  const handleRetry = () => {
    setSelectedOption(null);
    setSubmitted(false);
    setLastResult(null);
  };

  const handleSelectCount = (count) => {
    setQuestionCount(count);
    setCurrentIdx(0);
    setSelectedOption(null);
    setSubmitted(false);
    setLastResult(null);
    setCorrectCount(0);
  };

  return (
    <div className="workspace-page-root">
      {/* Header Bar */}
      <section className="atelier-page-header">
        <div className="header-meta-row">
          <span className="status-live-beacon" />
          <span className="coord-label">PRACTICE & MASTERY CHECKPOINT</span>
        </div>
        <div className="header-title-split">
          <div>
            <h1 className="page-heading">Practice & Mastery Questions</h1>
            <p className="page-subheading">
              Test your understanding of <strong>{activeConcept.title}</strong> with interactive mock questions.
            </p>
          </div>
          <div className="question-counter-badge">
            <span className="coord-label">
              QUESTION {currentIdx + 1} OF {activeQuestions.length} · SCORE: {correctCount}/{currentIdx + (submitted ? 1 : 0)}
            </span>
          </div>
        </div>

        {/* User Question Count Selector (5, 10, 15, 20) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginTop: '16px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border)'
        }}>
          <span className="coord-label" style={{ fontWeight: 600 }}>SELECT QUESTION SET:</span>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[5, 10, 15, 20].map(count => (
              <button
                key={count}
                type="button"
                onClick={() => handleSelectCount(count)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 'var(--radius-sharp)',
                  border: questionCount === count ? '1px solid var(--terracotta)' : '1px solid var(--border)',
                  backgroundColor: questionCount === count ? 'var(--terracotta)' : 'var(--surface-panel)',
                  color: questionCount === count ? '#FFFFFF' : 'var(--ink-secondary)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {count} Questions
              </button>
            ))}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--ink-muted)', marginLeft: 'auto' }}>
            Ready for backend mock question streaming
          </span>
        </div>
      </section>

      {/* Main 2-Column Split: Question & Form on Left, Textbook Reference on Right */}
      <div className="assessment-split-grid">
        {/* Left Column: Focused Diagnostic Question */}
        <div className="assessment-question-column">
          <div className="atelier-card question-card">
            <div className="card-top-bar">
              <span className="coord-label">TOPIC: {activeConcept.title.toUpperCase()}</span>
              <span className="card-badge-soft">PRACTICE CHECK</span>
            </div>

            <div className="question-body">
              <h2 className="question-prompt-text">{question.prompt}</h2>

              {/* Form Options */}
              <form onSubmit={handleSubmit} className="assessment-options-form">
                <div className="options-stack">
                  {question.options.map((option, idx) => {
                    const isSelected = selectedOption === idx;
                    let optionStatusClass = '';

                    if (submitted) {
                      if (idx === question.answer) {
                        optionStatusClass = 'correct-option';
                      } else if (isSelected && !lastResult?.isCorrect) {
                        optionStatusClass = 'incorrect-option';
                      }
                    }

                    return (
                      <label 
                        key={idx}
                        className={`option-choice-item ${isSelected ? 'selected' : ''} ${optionStatusClass}`}
                      >
                        <input 
                          type="radio" 
                          name="quiz-option"
                          checked={isSelected}
                          disabled={submitted}
                          onChange={() => setSelectedOption(idx)}
                          className="choice-radio-input"
                        />
                        <span className="choice-index-letter">
                          {String.fromCharCode(65 + idx)}
                        </span>
                        <span className="choice-text-label">{option}</span>
                      </label>
                    );
                  })}
                </div>

                {/* Submit / Continue Buttons */}
                <div className="question-actions-bar">
                  {!submitted ? (
                    <button 
                      type="submit" 
                      disabled={selectedOption === null}
                      className="btn-atelier-primary"
                    >
                      <span>Check My Answer</span>
                      <GlyphCheckmark size={12} />
                    </button>
                  ) : (
                    <div className="post-submission-buttons">
                      {!lastResult?.isCorrect && (
                        <button 
                          type="button" 
                          className="btn-atelier-outline"
                          onClick={handleRetry}
                        >
                          <GlyphRotate size={12} />
                          <span>Try Again</span>
                        </button>
                      )}
                      <button 
                        type="button" 
                        className="btn-atelier-primary"
                        onClick={handleNext}
                      >
                        <span>{isLastQuestion ? 'Complete Practice & View Roadmap' : 'Next Question'}</span>
                        <GlyphArrowRight size={12} />
                      </button>
                    </div>
                  )}
                </div>
              </form>
            </div>

            {/* Diagnostic Misconception Result Box */}
            {submitted && lastResult && (
              <div className={`assessment-result-drawer ${lastResult.isCorrect ? 'result-passed' : 'result-failed'}`}>
                <div className="result-header-row">
                  <div className="title-with-glyph">
                    {lastResult.isCorrect ? <GlyphCheckmark size={16} /> : <GlyphCrosshair size={16} />}
                    <h3 className="result-title">
                      {lastResult.isCorrect ? 'Correct! Well done.' : 'Review Needed'}
                    </h3>
                  </div>
                  <span className="coord-label">
                    {lastResult.isCorrect ? '+10 POINTS' : '0 POINTS'}
                  </span>
                </div>

                {!lastResult.isCorrect && (
                  <div className="misconception-callout-box">
                    <span className="coord-label">COMMON MISTAKE TO AVOID:</span>
                    <p className="misconception-text">{question.misconception}</p>
                  </div>
                )}

                <div className="result-explanation-box">
                  <span className="coord-label">EXPLANATION:</span>
                  <p className="explanation-text">{question.explanation}</p>
                </div>

                {!lastResult.isCorrect && (
                  <div className="result-remediation-cta">
                    <button 
                      type="button" 
                      className="btn-atelier-primary"
                      onClick={() => navigate('/app/studio')}
                    >
                      <span>Review This in Study Studio Notes</span>
                      <GlyphArrowRight size={12} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Grounded Curriculum Reference Plate */}
        <div className="assessment-plate-column">
          <div className="atelier-card figure-specimen-card">
            <div className="card-top-bar">
              <span className="coord-label">TEXTBOOK STUDY REFERENCE</span>
              <span className="card-badge-soft">PAGE 7</span>
            </div>

            <div className="figure-media-frame">
              <img src="/assets/notebook_handwritten.jpg" alt="Study Notes and Textbook Reference" className="figure-plate-img" />
              <div className="figure-caption-bar">
                <span>Database Systems Architecture · Chapter 3 Entity Integrity</span>
              </div>
            </div>

            <div className="figure-analysis-body">
              <span className="coord-label">QUICK RECAP:</span>
              <p className="figure-analysis-text">
                Primary keys enforce Entity Integrity. In relational theory, each row must be uniquely identifiable.
                If primary keys could be null, the system could not tell if a record is unknown or does not exist.
              </p>

              <div className="figure-properties-list">
                <div className="property-item">
                  <span className="prop-name">Uniqueness:</span>
                  <strong className="prop-val">Mandatory (100% Unique)</strong>
                </div>
                <div className="property-item">
                  <span className="prop-name">Nullability:</span>
                  <strong className="prop-val">Strictly Forbidden (NOT NULL)</strong>
                </div>
                <div className="property-item">
                  <span className="prop-name">Reference:</span>
                  <strong className="prop-val">Chapter 3, Page 7</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
