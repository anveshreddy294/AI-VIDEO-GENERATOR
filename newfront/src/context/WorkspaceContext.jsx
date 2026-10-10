import React, { createContext, useContext, useState } from 'react';
import { 
  ATELIER_SOURCES, 
  ATELIER_CONCEPTS, 
  ATELIER_ASSESSMENT_QUESTIONS,
  ATELIER_VIDEO_STORYBOARD,
  ATELIER_EDUCATOR_ANALYTICS 
} from '../services/atelierData';

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  // Session & User State
  const [user, setUser] = useState({
    name: 'Elena Rostova',
    email: 'elena.rostova@atelier.edu',
    role: 'student', // 'student' | 'educator'
    avatarLabel: 'ER',
    course: 'CS 304: Relational Database Systems'
  });

  const [sources, setSources] = useState(ATELIER_SOURCES);
  const [activeSourceId, setActiveSourceId] = useState('src-db-01');
  const [activeConceptId, setActiveConceptId] = useState('primary-key');
  const [isUploading, setIsUploading] = useState(false);
  
  // Learning Session State
  const [visitedConcepts, setVisitedConcepts] = useState(['relational-model', 'primary-key']);
  const [masteryScores, setMasteryScores] = useState({
    'relational-model': 94,
    'primary-key': 86,
    'foreign-key': 45,
    'first-normal-form': 68
  });

  // Diagnostic Remediation Tracking
  const [remediationsCompleted, setRemediationsCompleted] = useState({});
  const [assessmentAttempts, setAssessmentAttempts] = useState([]);

  // Grounded ASK Chat
  const [askHistory, setAskHistory] = useState([
    {
      sender: 'system',
      text: 'VisualAI is grounded in Database Systems Architecture (v2 · Chapter 3). You may query relational integrity, candidate keys, or normal forms.',
      citation: 'Source: Database_Systems_v2_Chapter3.pdf · Page 7, § 3.2'
    }
  ]);

  // Accessibility & Interface Settings
  const [reducedMotion, setReducedMotion] = useState(false);
  const [notification, setNotification] = useState(null);

  const notify = (msg) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3600);
  };

  const selectConcept = (conceptId) => {
    if (ATELIER_CONCEPTS[conceptId]) {
      setActiveConceptId(conceptId);
      if (!visitedConcepts.includes(conceptId)) {
        setVisitedConcepts(prev => [...prev, conceptId]);
      }
    }
  };

  const uploadSource = (file) => {
    setIsUploading(true);
    const newSource = {
      id: `src-upload-${Date.now()}`,
      name: file.name.replace(/\.[^/.]+$/, ''),
      filename: file.name,
      format: file.name.split('.').pop()?.toUpperCase() || 'PDF',
      subject: 'Ingested Material',
      pages: 12,
      size: `${(file.size / (1024 * 1024) || 1.8).toFixed(1)} MB`,
      version: 1,
      status: 'PROCESSING',
      conceptsCount: 4,
      coverPlate: '/assets/notebook_handwritten.jpg',
      opticalConfidence: '98.5%',
      summary: 'Ingestion pipeline initialized. Optical character segmentation and vector indexing underway.'
    };

    setSources(prev => [newSource, ...prev]);
    notify(`Ingested ${file.name}. Vector grounding in progress.`);

    setTimeout(() => {
      setSources(current => current.map(s => s.id === newSource.id ? { ...s, status: 'READY' } : s));
      setIsUploading(false);
      notify(`Verification complete for ${newSource.name}. Learning pathway structured.`);
    }, 3500);
  };

  const submitAssessmentAnswer = (questionId, selectedOption) => {
    const question = ATELIER_ASSESSMENT_QUESTIONS.find(q => q.id === questionId);
    if (!question) return { isCorrect: false, score: 0 };

    const isCorrect = selectedOption === question.answer;
    const newScore = isCorrect ? 92 : 45;

    setMasteryScores(prev => ({
      ...prev,
      [question.conceptId]: newScore
    }));

    if (isCorrect) {
      notify(`Invariant verified for ${question.conceptId.toUpperCase()}. Mastery: ${newScore}%.`);
    } else {
      notify(`Diagnostic gap flagged for ${question.conceptId.toUpperCase()}. Remediation recommended.`);
    }

    return {
      isCorrect,
      score: newScore,
      misconception: question.misconception,
      explanation: question.explanation
    };
  };

  const completeRemediation = (conceptId) => {
    setRemediationsCompleted(prev => ({ ...prev, [conceptId]: true }));
    setMasteryScores(prev => ({ ...prev, [conceptId]: Math.max(prev[conceptId] || 0, 85) }));
    notify(`Remediation walk-through completed for ${ATELIER_CONCEPTS[conceptId]?.title || conceptId}.`);
  };

  const toggleRole = () => {
    const nextRole = user.role === 'student' ? 'educator' : 'student';
    setUser(prev => ({
      ...prev,
      role: nextRole,
      name: nextRole === 'educator' ? 'Prof. David Vance' : 'Elena Rostova',
      avatarLabel: nextRole === 'educator' ? 'DV' : 'ER'
    }));
    notify(`Switched workspace to ${nextRole === 'student' ? 'Student Atelier' : 'Educator Console'} mode.`);
  };

  const activeSource = sources.find(s => s.id === activeSourceId) || sources[0];
  const activeConcept = ATELIER_CONCEPTS[activeConceptId] || ATELIER_CONCEPTS['primary-key'];

  return (
    <WorkspaceContext.Provider value={{
      user,
      setUser,
      toggleRole,
      sources,
      activeSource,
      setActiveSourceId,
      activeConcept,
      activeConceptId,
      setActiveConceptId: selectConcept,
      selectConcept,
      allConcepts: ATELIER_CONCEPTS,
      visitedConcepts,
      masteryScores,
      remediationsCompleted,
      completeRemediation,
      assessmentAttempts,
      assessmentQuestions: ATELIER_ASSESSMENT_QUESTIONS,
      submitAssessmentAnswer,
      videoStoryboard: ATELIER_VIDEO_STORYBOARD,
      educatorAnalytics: ATELIER_EDUCATOR_ANALYTICS,
      askHistory,
      setAskHistory,
      uploadSource,
      isUploading,
      reducedMotion,
      setReducedMotion,
      notification,
      showNotification: notify
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useAtelierWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useAtelierWorkspace must be used within WorkspaceProvider');
  return ctx;
}
