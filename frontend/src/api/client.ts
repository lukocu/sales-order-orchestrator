// The API identifies failures; views translate descriptors when they render.
export type ErrorParams = Record<string, string | number>

// Transitional compatibility with the previous backend. Never match arbitrary text.
const LEGACY_CODES: Record<string, string> = {
  'Not authenticated': 'NOT_AUTHENTICATED',
  'Invalid username or password': 'INVALID_CREDENTIALS',
  'Supervisor role required': 'SUPERVISOR_REQUIRED',
  'Database unavailable': 'DATABASE_UNAVAILABLE',
  'Login busy, try again': 'LOGIN_BUSY',
  'Inquiry not found': 'INQUIRY_NOT_FOUND',
  'Run not found': 'RUN_NOT_FOUND',
  'No analysis yet': 'NO_ANALYSIS',
  'Not Found': 'NOT_FOUND',
  'Reason is required': 'REASON_REQUIRED',
  'Analysis changed, reload': 'ANALYSIS_CHANGED',
  'Inquiry changed, reload': 'INQUIRY_CHANGED',
  'Draft changed, reload': 'DRAFT_CHANGED',
  'Inquiry awaiting supervisor decision': 'AWAITING_SUPERVISOR',
  'Draft already decided': 'DRAFT_DECIDED',
  'Draft cannot be changed': 'DRAFT_NOT_EDITABLE',
  'Draft is stale': 'DRAFT_STALE',
  'Policy verdict missing': 'POLICY_MISSING',
  'Draft is not awaiting supervisor': 'NOT_AWAITING_SUPERVISOR',
  'Cannot approve your own submission': 'OWN_SUBMISSION',
  'Nothing to orchestrate': 'NOTHING_TO_ORCHESTRATE',
  'Nothing to recommend': 'NOTHING_TO_RECOMMEND',
  'Nothing to evaluate': 'NOTHING_TO_EVALUATE',
  'Nothing to draft': 'NOTHING_TO_DRAFT',
  'Stored analysis is invalid': 'STORED_ANALYSIS_INVALID',
  'Checks failed': 'CHECKS_FAILED',
  'Orchestration failed': 'ORCHESTRATION_FAILED',
  'Recommendation failed': 'RECOMMENDATION_FAILED',
  'Policy evaluation failed': 'POLICY_FAILED',
  'Drafting failed': 'DRAFT_FAILED',
  'Decision failed': 'DECISION_FAILED',
  'LLM not configured': 'ANALYSIS_NOT_CONFIGURED',
  'LLM rate limit reached, try again later': 'ANALYSIS_RATE_LIMITED',
  'Analysis failed, try again': 'ANALYSIS_FAILED',
  'Mailbox not configured': 'MAILBOX_NOT_CONFIGURED',
  'Mailbox login failed': 'MAILBOX_AUTH_FAILED',
  'Mailbox unavailable': 'MAILBOX_UNAVAILABLE',
  'Mailbox error': 'MAILBOX_ERROR',
  'Mailbox fetch already in progress': 'MAILBOX_BUSY',
  'Quantity must be at least 1': 'INVALID_EDIT',
  'Unit price must be above zero': 'INVALID_EDIT',
  'Unit price must have at most two decimal places': 'INVALID_EDIT',
  "Edited lines must match the option's lines": 'INVALID_EDIT',
  "Option is not one of the recommendation's options": 'INVALID_EDIT',
  'API unreachable': 'NETWORK_ERROR',
  'Invalid response body': 'INVALID_RESPONSE',
}
const STATUS_CODES: Record<number, string> = {
  401: 'NOT_AUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND',
  405: 'METHOD_NOT_ALLOWED', 409: 'INQUIRY_CHANGED', 422: 'VALIDATION_ERROR',
  429: 'RATE_LIMITED',
}

function legacyCode(message: string, status: number | null): string {
  return Object.hasOwn(LEGACY_CODES, message) ? LEGACY_CODES[message] :
    (status === null ? 'UNKNOWN_ERROR' : STATUS_CODES[status] ?? 'HTTP_ERROR')
}

export class ApiError extends Error {
  readonly status: number | null
  readonly code: string
  readonly params: ErrorParams

  constructor(message: string, status: number | null = null, code?: string, params: ErrorParams = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code ?? legacyCode(message, status)
    this.params = params
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = 'Not authenticated', code?: string, params: ErrorParams = {}) {
    super(message, 401, code, params)
    this.name = 'UnauthorizedError'
  }
}

export function isAbortError(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError'
}

function paramsOf(value: unknown): ErrorParams {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return {}
  return Object.fromEntries(Object.entries(value).filter(([, item]) =>
    typeof item === 'string' || (typeof item === 'number' && Number.isFinite(item)),
  ))
}

async function readError(response: Response, signal?: AbortSignal | null): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (signal?.aborted || isAbortError(error)) throw error
    return response.status === 401
      ? new UnauthorizedError('Invalid response body', 'INVALID_RESPONSE')
      : new ApiError('Invalid response body', response.status, 'INVALID_RESPONSE')
  }
  const object = typeof body === 'object' && body !== null ? body as Record<string, unknown> : {}
  const detail = object.detail
  const validationMessages = Array.isArray(detail) ? detail.flatMap((item: unknown) => {
    if (typeof item !== 'object' || item === null) return []
    const message = (item as Record<string, unknown>).msg
    return typeof message === 'string' ? [message] : []
  }) : []
  const message = typeof detail === 'string' ? detail : validationMessages.length > 0
    ? validationMessages.join('; ') : `Unexpected response: HTTP ${response.status}`
  const code = typeof object.code === 'string' && object.code.length > 0
    ? object.code
    : Array.isArray(detail) && response.status === 422 ? 'VALIDATION_ERROR' : legacyCode(message, response.status)
  const params = paramsOf(object.params)
  return response.status === 401
    ? new UnauthorizedError(message, code, params)
    : new ApiError(message, response.status, code, params)
}

export async function request(
  path: string, init: RequestInit = {}, acceptedStatuses: readonly number[] = [],
): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    if (init.signal?.aborted || isAbortError(error)) throw error
    throw new ApiError('API unreachable', null, 'NETWORK_ERROR')
  }
  if (!response.ok && !acceptedStatuses.includes(response.status)) throw await readError(response, init.signal)
  return response
}

export async function requestJson<T>(
  path: string, isValid: (value: unknown) => value is T, init: RequestInit = {},
): Promise<T> {
  const response = await request(path, init)
  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (init.signal?.aborted || isAbortError(error)) throw error
    throw new ApiError('Invalid response body', response.status, 'INVALID_RESPONSE')
  }
  if (!isValid(body)) throw new ApiError('Invalid response body', response.status, 'INVALID_RESPONSE')
  return body
}
