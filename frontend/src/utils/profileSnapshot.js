export function buildProfileSnapshot(profile, subject) {
  if (!profile) return null;
  const cm = profile.confidence_map || {};
  const subj = subject || 'Physics';
  return {
    learner_id: profile.learner_id || '',
    name: profile.name || 'Learner',
    academic_level: profile.academic_level || 'class_11',
    exam_target: Array.isArray(profile.exam_target) ? profile.exam_target : [],
    learning_style: profile.learning_style || 'visual',
    pace_preference: profile.pace_preference || 'balanced',
    weak_subjects: Array.isArray(profile.weak_subjects) ? profile.weak_subjects : [],
    confidence_map: cm,
    subject_for_lesson: subj,
    subject_confidence: typeof cm[subj] === 'number' ? cm[subj] : 50,
  };
}
