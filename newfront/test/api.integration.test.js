import test from 'node:test';
import assert from 'node:assert/strict';

const sessionValues = new Map();
globalThis.window = {
  sessionStorage: {
    getItem: key => sessionValues.has(key) ? sessionValues.get(key) : null,
    setItem: (key, value) => sessionValues.set(key, String(value)),
    removeItem: key => sessionValues.delete(key)
  },
  setTimeout,
  clearTimeout
};

const { clearStoredSession, saveSession, jsonRequest } = await import('../src/services/api/client.js');
const { lessonApi } = await import('../src/services/api/lessonApi.js');
const { sourceApi } = await import('../src/services/api/sourceApi.js');
const { adaptLesson, adaptSource } = await import('../src/services/api/adapters.js');
const { ApiError, toUserMessage } = await import('../src/services/api/errors.js');

function response(payload, status = 200, headers = { 'content-type': 'application/json' }) {
  return new Response(payload === null ? null : JSON.stringify(payload), { status, headers });
}

test.afterEach(() => {
  clearStoredSession();
  globalThis.fetch = undefined;
});

test('lesson creation preserves backend content_id as the durable lesson identity', async () => {
  let request;
  globalThis.fetch = async (_url, options) => {
    request = { url: _url, options };
    return response({ content_id: 'lesson-content-1', topic: 'Binary Search Trees', explanation: 'server explanation' });
  };

  const created = await lessonApi.create({ topic: 'Binary Search Trees' });
  const body = JSON.parse(request.options.body);
  const adapted = adaptLesson({ lesson_id: created.content_id, topic: created.topic, content: created });

  assert.equal(request.url, '/educational-content');
  assert.deepEqual(body, { topic: 'Binary Search Trees' });
  assert.equal(adapted.id, 'lesson-content-1');
  assert.equal(adapted.content.explanation, 'server explanation');
});

test('expired sessions refresh once before authenticated lesson access', async () => {
  saveSession({ access_token: 'expired-access', refresh_token: 'refresh-1', expires_in: 3600 });
  const stored = JSON.parse(sessionValues.get('visualai.auth.session'));
  stored.expiresAt = Date.now() - 1;
  sessionValues.set('visualai.auth.session', JSON.stringify(stored));
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === '/api/auth/refresh') return response({ session: { access_token: 'fresh-access', refresh_token: 'fresh-refresh', expires_in: 3600 } });
    return response({ lessons: [] });
  };

  const result = await jsonRequest('/educational-content');
  assert.deepEqual(result, { lessons: [] });
  assert.equal(calls.filter(call => call.url === '/api/auth/refresh').length, 1);
  assert.equal(calls.at(-1).options.headers.get('Authorization'), 'Bearer fresh-access');
});

test('upload keeps the request multipart and does not set multipart Content-Type manually', async () => {
  let captured;
  saveSession({ access_token: 'access', refresh_token: 'refresh', expires_in: 3600 });
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return response({ job_id: 'job-1', status: 'pending', message: 'queued' });
  };

  const file = new File(['verified text'], 'lesson.txt', { type: 'text/plain' });
  const result = await sourceApi.uploadAndAssess(file);
  assert.equal(result.job_id, 'job-1');
  assert.equal(captured.url, '/pipeline/upload-and-assess');
  assert.equal(captured.options.body instanceof FormData, true);
  assert.equal(captured.options.headers.get('Content-Type'), null);
  assert.equal(captured.options.body.get('file').name, 'lesson.txt');
  assert.equal(captured.options.headers.get('Authorization'), 'Bearer access');
});

test('assessment submission and video status use the real lesson identity', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/assessment/submit')) return response({ percentage: 80, feedback: 'server graded' });
    return response({ job_id: 'video-1', status: 'QUEUED', stage: 'queued', progress: 0 });
  };

  const graded = await lessonApi.submitAssessment('lesson-42', { mcq_answers: { q1: 2 }, descriptive_answer: 'answer' });
  const status = await lessonApi.videoStatus('lesson-42');
  assert.equal(graded.percentage, 80);
  assert.equal(status.job_id, 'video-1');
  assert.equal(calls[0].url, '/educational-content/lesson-42/assessment/submit');
  assert.deepEqual(JSON.parse(calls[0].options.body), { mcq_answers: { q1: 2 }, descriptive_answer: 'answer' });
  assert.equal(calls[1].url, '/educational-content/lesson-42/video/status');
});

test('error taxonomy preserves backend codes and truthful user messaging', () => {
  const error = new ApiError('invalid lesson', { status: 422, code: 'EDUCATIONAL_CONTENT_INVALID' });
  assert.equal(error.code, 'EDUCATIONAL_CONTENT_INVALID');
  assert.match(toUserMessage(error), /backend validation/i);
  const source = adaptSource({ source_id: 'src-1', filename: 'lesson.txt', status: 'CONTENT_READY', content_ready: true, version: 1 });
  assert.equal(source.id, 'src-1');
  assert.equal(source.contentReady, true);
});
