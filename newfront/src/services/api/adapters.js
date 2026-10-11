const SOURCE_PLATES = [
  '/assets/chapter_source.jpg',
  '/assets/specimen_math_wave.jpg',
  '/assets/specimen_biology_dna.jpg',
  '/assets/chapter_knowledge.jpg',
  '/assets/notebook_handwritten.jpg',
  '/assets/plate_interferometer.jpg',
  '/assets/study_desk_mac.jpg',
  '/assets/specimen_analog_notebook.jpg',
  '/assets/chapter_evidence.jpg'
];

export function resolveSourceCoverPlate(filename, modality, sourceId) {
  const lower = String(filename || '').toLowerCase();
  const mod = String(modality || '').toLowerCase();
  if (lower.includes('math') || lower.includes('calculus') || lower.includes('wave')) return '/assets/specimen_math_wave.jpg';
  if (lower.includes('bio') || lower.includes('cell') || lower.includes('dna')) return '/assets/specimen_biology_dna.jpg';
  if (lower.includes('physic') || lower.includes('orbit') || lower.includes('gravity')) return '/assets/specimen_physics_orbit.jpg';
  if (lower.includes('code') || lower.includes('sql') || lower.includes('db') || lower.includes('tree')) return '/assets/database_code_screen.jpg';
  if (lower.includes('note') || lower.includes('draft') || mod === 'text' || lower.endsWith('.txt')) return '/assets/notebook_handwritten.jpg';
  if (mod === 'image' || lower.endsWith('.png') || lower.endsWith('.jpg')) return '/assets/plate_interferometer.jpg';
  if (lower.endsWith('.pdf')) return '/assets/chapter_source.jpg';

  const hash = String(sourceId || filename || 'src').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return SOURCE_PLATES[hash % SOURCE_PLATES.length];
}

export function adaptSource(source) {
  if (!source) return null;
  const filename = source.filename || source.name || 'Unnamed source';
  const modality = source.modality || source.source_type || 'source';
  const analysis = source.analysis && typeof source.analysis === 'object' ? source.analysis : {};
  return {
    id: source.source_id,
    name: filename.replace(/\.[^/.]+$/, ''),
    filename,
    format: String(modality).toUpperCase(),
    subject: 'Uploaded material',
    pages: null,
    size: null,
    version: source.version ?? 1,
    status: source.status || 'UNKNOWN',
    contentReady: source.content_ready === true,
    conceptsCount: analysis.concepts_count ?? source.concepts_count ?? null,
    coverPlate: resolveSourceCoverPlate(filename, modality, source.source_id),
    opticalConfidence: null,
    summary: humanSourceStatus(source.status)
  };
}

export function adaptLessonSummary(summary) {
  return {
    ...summary,
    id: summary.lesson_id,
    title: summary.topic || 'Untitled lesson',
    conceptCount: summary.concept_count ?? (summary.content?.key_concepts?.length ?? 0)
  };
}

export function adaptLesson(detail) {
  if (!detail) return null;
  return {
    ...detail,
    id: detail.lesson_id,
    content: detail.content || null,
    topic: detail.topic || detail.content?.topic || 'Untitled lesson'
  };
}

export function statusLabel(status) {
  return String(status || 'UNKNOWN').replaceAll('_', ' ');
}

export function humanSourceStatus(status) {
  const value = String(status || '').toUpperCase();
  if (value === 'READY') return 'Ready to learn';
  if (value === 'CONTENT_READY') return 'Material read · search preparing';
  if (['PROCESSING', 'EXTRACTING', 'NORMALIZING', 'PERSISTING'].includes(value)) return 'Reading your material';
  if (value === 'INDEXING') return 'Preparing document search';
  if (value === 'FAILED' || value.includes('FAILED')) return 'Could not process this file';
  return 'Preparing learning content';
}

export function humanJobStage(stage, status) {
  const value = String(stage || status || '').toUpperCase();
  if (value.includes('EXTRACT') || value.includes('INGEST')) return 'Reading your material';
  if (value.includes('INDEX')) return 'Preparing document search';
  if (value.includes('CONTENT_READY') || value.includes('SOURCE_READY')) return 'Preparing learning content';
  if (value.includes('FAIL')) return 'Could not process this file';
  if (value.includes('COMPLETE') || value === 'READY') return 'Ready to learn';
  return 'Preparing learning content';
}
