// Shared fetch wrapper for the session-protected API. A 401 becomes an
// UnauthorizedError so the UI can return to the sign-in form; every other failure
// (network, 4xx/5xx, malformed body) becomes an ApiError with a readable message.
// An aborted request rethrows the original AbortError.

export class UnauthorizedError extends Error {
  constructor(message = 'Not authenticated') {
    super(message)
    this.name = 'UnauthorizedError'
  }
}

export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null) {
      const detail = (body as Record<string, unknown>).detail
      if (typeof detail === 'string') return detail
      // FastAPI request validation (422): a list of errors, each with a `msg`.
      if (Array.isArray(detail)) {
        const messages = detail
          .map((item: unknown) =>
            typeof item === 'object' && item !== null ? (item as Record<string, unknown>).msg : null,
          )
          .filter((msg): msg is string => typeof msg === 'string')
        if (messages.length > 0) return messages.join('; ')
      }
    }
  } catch {
    // Not JSON; fall back to the generic message.
  }
  return null
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    if (init.signal?.aborted) throw error
    throw new ApiError('API unreachable')
  }

  if (response.status === 401) {
    throw new UnauthorizedError((await readDetail(response)) ?? undefined)
  }
  if (!response.ok) {
    const detail = await readDetail(response)
    throw new ApiError(detail ?? `Unexpected response: HTTP ${response.status}`, response.status)
  }
  return response
}

export async function requestJson<T>(
  path: string,
  isValid: (value: unknown) => value is T,
  init: RequestInit = {},
): Promise<T> {
  const response = await request(path, init)
  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (init.signal?.aborted) throw error
    throw new ApiError('Invalid response body', response.status)
  }
  if (!isValid(body)) {
    throw new ApiError('Invalid response body', response.status)
  }
  return body
}
