export class ApiError extends Error {
  constructor(message, { status = 0, code = 'UNKNOWN_ERROR', detail = null, retryable = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.retryable = retryable;
  }
}

function detailObject(detail) {
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return detail;
  return null;
}

export function errorCodeForStatus(status) {
  return {
    401: 'AUTHENTICATION_REQUIRED',
    403: 'PERMISSION_DENIED',
    404: 'RESOURCE_NOT_FOUND',
    409: 'RESOURCE_CONFLICT',
    413: 'UPLOAD_TOO_LARGE',
    422: 'REQUEST_INVALID',
    429: 'RATE_LIMITED',
    500: 'SERVER_ERROR',
    502: 'UPSTREAM_UNAVAILABLE',
    503: 'SERVICE_UNAVAILABLE',
    504: 'UPSTREAM_TIMEOUT'
  }[status] || 'REQUEST_FAILED';
}

export async function parseApiError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Some FastAPI errors have an empty body.
  }

  const detail = payload?.detail ?? payload?.error ?? payload;
  const objectDetail = detailObject(detail);
  const code = objectDetail?.code || payload?.code || errorCodeForStatus(response.status);
  const message = objectDetail?.message || (typeof detail === 'string' ? detail : null) ||
    `Request failed (${response.status})`;

  return new ApiError(message, {
    status: response.status,
    code,
    detail: payload,
    retryable: objectDetail?.retryable === true || [429, 500, 502, 503, 504].includes(response.status)
  });
}

export function toUserMessage(error) {
  if (error?.name === 'AbortError') return 'The request was cancelled.';
  if (error?.name === 'TypeError') return 'The VisualAI service could not be reached. Check that FastAPI is running on port 8000.';
  if (!(error instanceof ApiError)) return 'Something went wrong. Please try again.';
  if (error.code === 'EDUCATIONAL_CONTENT_INVALID') return 'The lesson response did not pass backend validation. No lesson was saved; retry generation.';
  if (error.code === 'CONTENT_UNAVAILABLE') return 'This content is not available for your account.';
  if (error.code === 'LESSON_NOT_FOUND') return 'This lesson no longer exists or is not available to your account.';
  if (error.code === 'VIDEO_NOT_READY') return 'The video artifact is not ready yet.';
  if (error.code === 'VISION_EXTRACTION_FAILED' || error.code === 'EXTRACTION_INSUFFICIENT') return 'The source could not produce enough verified content. Review the source status and retry when available.';
  if (error.status === 401) return 'Your session expired. Sign in again to continue.';
  if (error.status === 403) return 'You are not authorized to access this resource.';
  if (error.status === 413) return 'That file exceeds the backend upload limit.';
  if (error.status === 422) return error.message || 'The request did not pass backend validation.';
  if (error.status === 429) return 'The service is busy or rate-limited. Please retry later.';
  if (error.status >= 500) return 'A backend or provider service is temporarily unavailable. Retry when it is available.';
  return error.message;
}
