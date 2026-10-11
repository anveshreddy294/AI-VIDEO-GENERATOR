// Presentation only. State comes from job snapshots and canonical source records.
export const UPLOAD_WORKFLOW_STEPS = [
  { key: 'upload', label: 'Upload' }, { key: 'read', label: 'Read' },
  { key: 'save', label: 'Save' }, { key: 'search', label: 'Search' }
];
export const VIDEO_WORKFLOW_STEPS = [
  { key: 'queued', label: 'Prepare' }, { key: 'audio', label: 'Narrate' },
  { key: 'render', label: 'Compose' }, { key: 'ready', label: 'Ready' }
];
const upper = value => String(value || '').toUpperCase();
const uploadStageKey = stage => ({
  UPLOADING: 'upload', QUEUED: 'upload', INGESTING_SOURCE: 'read',
  EXTRACTING_SOURCE: 'read', PREPARING_IMAGE: 'read', UNDERSTANDING_IMAGE: 'read',
  VALIDATING_VISUAL_EVIDENCE: 'read', EXTRACTION: 'read', NORMALIZATION: 'read',
  PERSISTING_SOURCE: 'save', PERSISTENCE: 'save', BUILDING_LEARNING_STRUCTURE: 'save',
  INDEXING_SOURCE: 'search', INDEXING: 'search'
})[upper(stage)];

export function uploadWorkflowState(job, source, error = null) {
  const states = {};
  const sourceId = job?.result?.source_id || job?.metadata?.source_id;
  const matchingSource = !job || (sourceId && sourceId === (source?.id || source?.source_id)) ? source : null;
  const status = upper(job?.status);
  const stage = upper(job?.current_stage);
  const canonicalStatus = upper(matchingSource?.status || job?.source_lifecycle);
  if (job?.job_id || matchingSource) states.upload = 'completed';
  if (matchingSource?.contentReady || matchingSource?.content_ready || job?.result?.content_ready || canonicalStatus === 'CONTENT_READY') {
    Object.assign(states, { upload: 'completed', read: 'completed', save: 'completed' });
  }
  // Terminal errors take precedence over a retained current_stage. An unknown
  // failure stage is reported at workflow level rather than guessed as extraction.
  const terminal = error || status === 'FAILED' || canonicalStatus === 'FAILED' ? 'failed'
    : ['CANCELLED', 'CANCELED'].includes(status) || ['CANCELLED', 'CANCELED'].includes(canonicalStatus) ? 'cancelled' : null;
  if (terminal) {
    const key = uploadStageKey(job?.failure?.stage || stage);
    if (key) states[key] = terminal;
    return { states, outcome: terminal, message: terminal === 'failed' ? 'Processing failed. Review the error below before retrying.' : 'Processing was cancelled.' };
  }
  if (canonicalStatus === 'READY' || (status === 'COMPLETED' && stage === 'SOURCE_READY')) {
    return { states: Object.fromEntries(UPLOAD_WORKFLOW_STEPS.map(step => [step.key, 'completed'])), message: 'Material and document search are ready.' };
  }
  if (canonicalStatus === 'CONTENT_READY' || (status === 'COMPLETED' && (stage === 'CONTENT_READY' || job?.result?.content_ready))) {
    return { states: { upload: 'completed', read: 'completed', save: 'completed' }, message: 'Material is ready to use. Optional document search has not completed.' };
  }
  if (job?.is_finished || status === 'COMPLETED') return { states, message: 'Processing ended. Search readiness has not been confirmed.' };
  const key = uploadStageKey(stage || canonicalStatus);
  if (key === 'save') Object.assign(states, { upload: 'completed', read: 'completed' });
  if (key === 'search') Object.assign(states, { upload: 'completed', read: 'completed', save: 'completed' });
  if (key && !(key === 'upload' && states.upload === 'completed')) states[key] = 'active';
  return { states, message: key ? 'Processing your material. Status updates as work is reported.' : 'Waiting for a processing update.' };
}

export function videoWorkflowState(snapshot) {
  const status = upper(typeof snapshot === 'string' ? snapshot : snapshot?.status);
  const states = {};
  if (status === 'COMPLETED') return { states: Object.fromEntries(VIDEO_WORKFLOW_STEPS.map(step => [step.key, 'completed'])), message: 'Your video is ready.' };
  if (['FAILED', 'CANCELLED', 'CANCELED'].includes(status)) {
    // The engine replaces stage with FAILED on error. It supplies no reliable
    // last successful milestone, so do not claim narration or composition passed.
    if (snapshot?.job_id) states.queued = 'completed';
    return { states, outcome: status === 'FAILED' ? 'failed' : 'cancelled', message: status === 'FAILED' ? 'Video generation failed. The service did not confirm which steps completed.' : 'Video generation was cancelled.' };
  }
  if (['QUEUED', 'PLANNING'].includes(status)) states.queued = 'active';
  if (['GENERATING_AUDIO', 'ALIGNING'].includes(status)) Object.assign(states, { queued: 'completed', audio: 'active' });
  if (['RENDERING', 'COMPOSITING'].includes(status)) Object.assign(states, { queued: 'completed', audio: 'completed', render: 'active' });
  return { states, message: Object.keys(states).length ? 'Preparing your video. Each step reflects the reported job state.' : 'Video generation has not started.' };
}
