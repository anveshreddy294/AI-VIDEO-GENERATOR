import { jsonRequest, requestTimeouts } from './client.js';

export const sourceApi = {
  list: () => jsonRequest('/sources'),
  get: sourceId => jsonRequest(`/sources/${encodeURIComponent(sourceId)}`),
  version: (sourceId, version) => jsonRequest(`/sources/${encodeURIComponent(sourceId)}/versions/${version}`),
  contentUnits: (sourceId, version) => jsonRequest(`/sources/${encodeURIComponent(sourceId)}/content-units${version ? `?version=${version}` : ''}`),
  uploadAndAssess: file => {
    const body = new FormData();
    body.append('file', file);
    return jsonRequest('/pipeline/upload-and-assess', { method: 'POST', body, timeoutMs: requestTimeouts.upload });
  },
  job: jobId => jsonRequest(`/pipeline/jobs/${encodeURIComponent(jobId)}`),
  retryJob: jobId => jsonRequest(`/pipeline/jobs/${encodeURIComponent(jobId)}/retry`, { method: 'POST' })
};
