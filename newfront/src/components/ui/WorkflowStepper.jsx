import React from 'react';

const STATE_LABELS = { pending: 'Not started', active: 'In progress', completed: 'Complete', failed: 'Failed', cancelled: 'Cancelled' };

export function WorkflowStepper({ steps, states = {}, message, outcome, label = 'Processing status' }) {
  return (
    <div className={`workflow-status ${outcome ? `workflow-status-${outcome}` : ''}`}>
      <ol className="workflow-stepper" aria-label={label}>
        {steps.map((step, index) => {
          const state = STATE_LABELS[states[step.key]] ? states[step.key] : 'pending';
          return (
            <li key={step.key} className={`workflow-step workflow-step-${state}`} aria-current={state === 'active' ? 'step' : undefined}>
              <span className="workflow-step-node" aria-hidden="true">{index + 1}</span>
              <span className="workflow-step-copy"><strong>{step.label}</strong><small>{STATE_LABELS[state]}</small></span>
            </li>
          );
        })}
      </ol>
      {message && <p className="workflow-message" role="status">{message}</p>}
    </div>
  );
}
