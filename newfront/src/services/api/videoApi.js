import { apiRequest, jsonRequest } from './client.js';
import { lessonApi } from './lessonApi.js';

export const videoApi = {
  start: lessonApi.startVideo,
  status: lessonApi.videoStatus,
  stream: async lessonId => {
    const response = await apiRequest(lessonApi.videoStreamPath(lessonId), { method: 'GET', timeoutMs: 120_000 });
    const contentLength = Number(response.headers.get('content-length') || 0);
    if (contentLength > 250 * 1024 * 1024) throw new Error('The video artifact exceeds the browser playback download limit.');
    return response.blob();
  },
  // Kept as a named service boundary for future metadata additions; no unverified URLs are used.
  statusJson: lessonId => jsonRequest(`/educational-content/${encodeURIComponent(lessonId)}/video/status`)
};
