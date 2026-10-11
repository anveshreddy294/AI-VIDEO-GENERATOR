import { jsonRequest, requestTimeouts } from './client.js';

export const lessonApi = {
  list: () => jsonRequest('/educational-content'),
  get: lessonId => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}`),
  create: request => jsonRequest('/educational-content', { method: 'POST', body: request, timeoutMs: requestTimeouts.generation }),
  notes: (lessonId, options = {}) => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/notes`, { method: 'POST', body: options, timeoutMs: requestTimeouts.generation }),
  diagram: (lessonId, options = {}) => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/diagram`, { method: 'POST', body: options, timeoutMs: requestTimeouts.generation }),
  assessment: lessonId => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/assessment`, { method: 'POST', timeoutMs: requestTimeouts.generation }),
  submitAssessment: (lessonId, submission) => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/assessment/submit`, { method: 'POST', body: submission, timeoutMs: requestTimeouts.generation }),
  ask: (lessonId, question) => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/ask`, { method: 'POST', body: { question }, timeoutMs: requestTimeouts.generation }),
  startVideo: lessonId => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/video`, { method: 'POST', timeoutMs: requestTimeouts.generation }),
  videoStatus: lessonId => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/video/status`),
  videoStreamPath: lessonId => `/educational-content/${encodeURIComponent(lessonId)}/video/stream`
};
