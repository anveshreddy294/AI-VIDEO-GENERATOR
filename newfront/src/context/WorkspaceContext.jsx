import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { authApi } from '../services/api/authApi';
import { lessonApi } from '../services/api/lessonApi';
import { sourceApi } from '../services/api/sourceApi';
import { adaptLesson, adaptLessonSummary, adaptSource } from '../services/api/adapters';
import { ApiError, toUserMessage } from '../services/api/errors';
import { getStoredSession, clearStoredSession } from '../services/api/client';

const WorkspaceContext = createContext(null);
const ACTIVE_SOURCE_KEY = 'visualai.workspace.activeSourceId';
const ACTIVE_LESSON_KEY = 'visualai.workspace.activeLessonId';
const SUPPORTED_UPLOADS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'txt', 'mp4', 'mov', 'mkv'];

function identityToUser(identity) {
  const profile = identity?.profile || {};
  const role = profile.role || 'student';
  const name = profile.full_name || identity?.email || 'VisualAI learner';
  return {
    id: identity?.user_id,
    name,
    email: identity?.email || '',
    role: ['instructor', 'admin'].includes(role) ? 'educator' : role,
    backendRole: role,
    avatarLabel: name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase() || 'VA',
    course: null
  };
}

function lessonToConcepts(lesson) {
  const content = lesson?.content;
  if (!content) return {};
  return Object.fromEntries((content.key_concepts || []).map((concept, index) => {
    const id = `concept-${index + 1}`;
    return [id, {
      id,
      title: concept.name,
      name: concept.name,
      explanation: concept.explanation,
      summary: concept.explanation,
      prerequisites: [],
      page: null,
      formula: null
    }];
  }));
}

export function WorkspaceProvider({ children }) {
  const [authStatus, setAuthStatus] = useState(() => getStoredSession() ? 'loading' : 'unauthenticated');
  const [authError, setAuthError] = useState(null);
  const [identity, setIdentity] = useState(null);
  const [sources, setSources] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [activeSourceId, setActiveSourceIdState] = useState(() => window.sessionStorage.getItem(ACTIVE_SOURCE_KEY));
  const [activeLessonId, setActiveLessonIdState] = useState(() => window.sessionStorage.getItem(ACTIVE_LESSON_KEY));
  const [activeLesson, setActiveLesson] = useState(null);
  const [workspaceStatus, setWorkspaceStatus] = useState('idle');
  const [workspaceError, setWorkspaceError] = useState(null);
  const [uploadJob, setUploadJob] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [videoJobStatus, setVideoJobStatus] = useState(null);
  const [notification, setNotification] = useState(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const notificationTimer = useRef(null);
  const uploadPollRef = useRef(null);
  const activeSourceIdRef = useRef(activeSourceId);
  const activeLessonIdRef = useRef(activeLessonId);

  const notify = useCallback(message => {
    setNotification(message);
    window.clearTimeout(notificationTimer.current);
    notificationTimer.current = window.setTimeout(() => setNotification(null), 4200);
  }, []);

  const setActiveSourceId = useCallback(sourceId => {
    activeSourceIdRef.current = sourceId || null;
    setActiveSourceIdState(sourceId || null);
    if (sourceId) window.sessionStorage.setItem(ACTIVE_SOURCE_KEY, sourceId);
    else window.sessionStorage.removeItem(ACTIVE_SOURCE_KEY);
  }, []);

  const setActiveLessonId = useCallback(lessonId => {
    activeLessonIdRef.current = lessonId || null;
    setActiveLessonIdState(lessonId || null);
    if (lessonId) window.sessionStorage.setItem(ACTIVE_LESSON_KEY, lessonId);
    else window.sessionStorage.removeItem(ACTIVE_LESSON_KEY);
  }, []);

  const restoreIdentity = useCallback(async () => {
    if (!getStoredSession()) {
      setAuthStatus('unauthenticated');
      return null;
    }
    setAuthStatus('loading');
    try {
      const result = await authApi.me();
      setIdentity(result);
      setAuthStatus('authenticated');
      setAuthError(null);
      return result;
    } catch (error) {
      clearStoredSession();
      setIdentity(null);
      setAuthStatus('unauthenticated');
      setAuthError(error);
      return null;
    }
  }, []);

  useEffect(() => {
    restoreIdentity();
    return () => {
      window.clearTimeout(notificationTimer.current);
      window.clearTimeout(uploadPollRef.current);
    };
  }, [restoreIdentity]);

  const login = useCallback(async (email, password) => {
    setAuthStatus('loading');
    setAuthError(null);
    try {
      const result = await authApi.login(email.trim(), password);
      if (!result.session) throw new ApiError('Login did not return an active session', { status: 401, code: 'AUTHENTICATION_REQUIRED' });
      const current = await authApi.me();
      setIdentity(current);
      setAuthStatus('authenticated');
      notify('Authenticated session established.');
      return current;
    } catch (error) {
      setAuthStatus('unauthenticated');
      setAuthError(error);
      throw error;
    }
  }, [notify]);

  const signup = useCallback(async (email, password, fullName) => {
    setAuthStatus('loading');
    setAuthError(null);
    try {
      const result = await authApi.signup(email.trim(), password, fullName.trim());
      if (result.confirmation_required || !result.session) {
        setAuthStatus('unauthenticated');
        notify('Account created. Confirm your email with Supabase before signing in.');
        return { confirmationRequired: true };
      }
      const current = await authApi.me();
      setIdentity(current);
      setAuthStatus('authenticated');
      notify('Account created and authenticated.');
      return current;
    } catch (error) {
      setAuthStatus('unauthenticated');
      setAuthError(error);
      throw error;
    }
  }, [notify]);

  const logout = useCallback(async () => {
    window.clearTimeout(uploadPollRef.current);
    try { await authApi.logout(); } finally {
      setIdentity(null);
      setSources([]);
      setLessons([]);
      setActiveLesson(null);
      setActiveSourceId(null);
      setActiveLessonId(null);
      setUploadJob(null);
      setUploadError(null);
      setVideoJobStatus(null);
      setAuthStatus('unauthenticated');
      notify('Signed out of the verified workspace.');
    }
  }, [notify, setActiveLessonId, setActiveSourceId]);

  const loadSources = useCallback(async () => {
    const result = await sourceApi.list();
    const next = (result?.sources || []).map(adaptSource).filter(source => source.id);
    setSources(next);
    if (activeSourceIdRef.current && !next.some(source => source.id === activeSourceIdRef.current)) setActiveSourceId(null);
    if (!activeSourceIdRef.current && next[0]) setActiveSourceId(next[0].id);
    return next;
  }, [setActiveSourceId]);

  const loadLessons = useCallback(async () => {
    const result = await lessonApi.list();
    const next = (result?.lessons || []).map(adaptLessonSummary).filter(lesson => lesson.id);
    setLessons(next);
    if (activeLessonIdRef.current && !next.some(lesson => lesson.id === activeLessonIdRef.current)) setActiveLessonId(null);
    if (!activeLessonIdRef.current && next[0]) setActiveLessonId(next[0].id);
    return next;
  }, [setActiveLessonId]);

  useEffect(() => {
    if (authStatus !== 'authenticated') return undefined;
    let cancelled = false;
    setWorkspaceStatus('loading');
    Promise.all([loadSources(), loadLessons()]).then(() => {
      if (!cancelled) {
        setWorkspaceStatus('ready');
        setWorkspaceError(null);
      }
    }).catch(error => {
      if (!cancelled) {
        setWorkspaceStatus('error');
        setWorkspaceError(error);
      }
    });
    return () => { cancelled = true; };
  }, [authStatus, loadSources, loadLessons]);

  const loadLesson = useCallback(async lessonId => {
    if (!lessonId) {
      setActiveLesson(null);
      return null;
    }
    const result = adaptLesson(await lessonApi.get(lessonId));
    setActiveLesson(result);
    setActiveLessonId(result?.id || null);
    return result;
  }, [setActiveLessonId]);

  useEffect(() => {
    if (authStatus !== 'authenticated' || !activeLessonId) {
      if (!activeLessonId) setActiveLesson(null);
      return undefined;
    }
    let cancelled = false;
    loadLesson(activeLessonId).catch(error => {
      if (!cancelled) {
        setActiveLesson(null);
        setWorkspaceError(error);
      }
    });
    return () => { cancelled = true; };
  }, [authStatus, activeLessonId, loadLesson]);

  const createLesson = useCallback(async ({ topic, sourceId, sourceVersion } = {}) => {
    const request = { topic: topic?.trim() || undefined };
    if (sourceId) {
      request.source_id = sourceId;
      request.source_version = Number(sourceVersion);
    }
    const created = await lessonApi.create(request);
    const result = adaptLesson({
      lesson_id: created?.content_id,
      topic: created?.topic,
      source_id: created?.source_id,
      source_version: created?.source_version,
      content: created
    });
    setActiveLesson(result);
    setActiveLessonId(result.id);
    setLessons(previous => [adaptLessonSummary(result), ...previous.filter(lesson => lesson.id !== result.id)]);
    return result;
  }, [setActiveLessonId]);

  const pollUploadJob = useCallback(async jobId => {
    window.clearTimeout(uploadPollRef.current);
    const job = await sourceApi.job(jobId);
    setUploadJob(job);
    if (job.is_finished || ['completed', 'warning', 'failed', 'cancelled'].includes(job.status)) {
      await loadSources();
      if (job.status === 'completed' && (job.result?.source_id || job.metadata?.source_id)) {
        setActiveSourceId(job.result?.source_id || job.metadata.source_id);
        notify('Source processing completed. Verified source metadata is now available.');
      } else if (job.status === 'failed') {
        const code = job.failure?.code || job.metadata?.error_code || job.error || 'SOURCE_PROCESSING_FAILED';
        setUploadError(new ApiError('Source processing failed', { code, status: 422, retryable: true }));
      }
      return job;
    }
    uploadPollRef.current = window.setTimeout(() => pollUploadJob(jobId), 2000);
    return job;
  }, [loadSources, notify, setActiveSourceId]);

  const uploadSource = useCallback(async file => {
    const extension = file?.name?.split('.').pop()?.toLowerCase();
    if (!file || !SUPPORTED_UPLOADS.includes(extension)) {
      const error = new ApiError('This file type is not accepted by the backend.', { status: 415, code: 'UNSUPPORTED_FILE_TYPE' });
      setUploadError(error);
      notify(toUserMessage(error));
      throw error;
    }
    if (file.size > 200 * 1024 * 1024) {
      const error = new ApiError('Upload exceeds the backend limit.', { status: 413, code: 'UPLOAD_TOO_LARGE' });
      setUploadError(error);
      notify(toUserMessage(error));
      throw error;
    }
    setUploadError(null);
    setUploadJob({ status: 'pending', current_stage: 'uploading', progress_percent: 0, events: [] });
    try {
      const created = await sourceApi.uploadAndAssess(file);
      await pollUploadJob(created.job_id);
      return created;
    } catch (error) {
      setUploadError(error);
      notify(toUserMessage(error));
      throw error;
    }
  }, [notify, pollUploadJob]);

  const retryUpload = useCallback(async () => {
    if (!uploadJob?.job_id) return null;
    setUploadError(null);
    try {
      const retry = await sourceApi.retryJob(uploadJob.job_id);
      setUploadJob(retry);
      await pollUploadJob(retry.job_id || uploadJob.job_id);
      return retry;
    } catch (error) {
      setUploadError(error);
      notify(toUserMessage(error));
      throw error;
    }
  }, [notify, pollUploadJob, uploadJob]);

  const activeSource = useMemo(() => sources.find(source => source.id === activeSourceId) || null, [sources, activeSourceId]);
  const allConcepts = useMemo(() => lessonToConcepts(activeLesson), [activeLesson]);
  const activeConcept = Object.values(allConcepts)[0] || null;
  const user = useMemo(() => identityToUser(identity), [identity]);

  const value = {
    authStatus, authError, identity, user, login, signup, logout, restoreIdentity,
    sources, lessons, activeSource, activeSourceId, setActiveSourceId,
    activeLessonId, setActiveLessonId, activeLesson, loadLesson, createLesson,
    loadSources, loadLessons, workspaceStatus, workspaceError,
    uploadSource, retryUpload, uploadJob, uploadError, isUploading: Boolean(uploadJob && !uploadJob.is_finished && !['completed', 'failed', 'cancelled'].includes(uploadJob.status)),
    videoJobStatus, setVideoJobStatus,
    activeConcept, activeConceptId: activeConcept?.id || null, allConcepts,
    reducedMotion, setReducedMotion, notification, notify, showNotification: notify,
    toUserMessage
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useAtelierWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useAtelierWorkspace must be used within WorkspaceProvider');
  return context;
}
