import test from 'node:test';
import assert from 'node:assert/strict';
import { uploadWorkflowState, videoWorkflowState } from '../src/services/workflowState.js';

test('CONTENT_READY ends extraction without pretending optional search is running or complete', () => {
  const result = uploadWorkflowState({ job_id: 'j', status: 'completed', current_stage: 'content_ready', is_finished: true, result: { content_ready: true } });
  assert.deepEqual(result.states, { upload: 'completed', read: 'completed', save: 'completed' });
  assert.match(result.message, /Optional/);
});
test('a retained running stage cannot mask failure or cancellation', () => {
  const failed = uploadWorkflowState({ job_id: 'j', status: 'failed', current_stage: 'EXTRACTING_SOURCE' });
  assert.equal(failed.states.read, 'failed');
  assert.equal(failed.states.search, undefined);
  const cancelled = uploadWorkflowState({ job_id: 'j', status: 'cancelled', current_stage: 'INDEXING_SOURCE' });
  assert.equal(cancelled.states.search, 'cancelled');
  assert.equal(cancelled.states.read, undefined, 'A terminal failure stage is not proof earlier work succeeded');
});
test('an unrelated ready source never completes the current upload', () => {
  const result = uploadWorkflowState({ job_id: 'j', status: 'running', current_stage: 'EXTRACTING_SOURCE', metadata: { source_id: 'new' } }, { id: 'old', status: 'READY', contentReady: true });
  assert.equal(result.states.read, 'active');
  assert.equal(result.states.search, undefined);
});
test('saved source readiness remains authoritative after completion polling', () => {
  const result = uploadWorkflowState({ job_id: 'j', status: 'completed', current_stage: 'content_ready', result: { source_id: 's', content_ready: true } }, { id: 's', status: 'READY' });
  assert.equal(result.states.search, 'completed');
});
test('an upload transport error does not leave the local uploading stage active', () => {
  const result = uploadWorkflowState({ status: 'pending', current_stage: 'uploading' }, null, new Error('offline'));
  assert.deepEqual(result.states, { upload: 'failed' });
});
test('unknown and unstarted video states do not claim a queued request', () => {
  for (const status of [undefined, 'NOT_STARTED', 'UNKNOWN']) assert.deepEqual(videoWorkflowState(status).states, {});
});
test('video failure without milestone history never invents narration success', () => {
  const failed = videoWorkflowState({ job_id: 'v', status: 'FAILED', stage: 'FAILED', progress: 90 });
  assert.equal(failed.outcome, 'failed');
  assert.equal(failed.states.audio, undefined);
  assert.equal(failed.states.render, undefined);
  assert.equal(videoWorkflowState('CANCELLED').outcome, 'cancelled');
});
test('known engine phases and validated completion expose their confirmed milestones', () => {
  assert.deepEqual(videoWorkflowState('ALIGNING').states, { queued: 'completed', audio: 'active' });
  assert.deepEqual(videoWorkflowState('COMPOSITING').states, { queued: 'completed', audio: 'completed', render: 'active' });
  assert.deepEqual(videoWorkflowState('COMPLETED').states, { queued: 'completed', audio: 'completed', render: 'completed', ready: 'completed' });
});
