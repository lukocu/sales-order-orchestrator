import { ApiError, isAbortError, request } from './client'
import { describeError, type ErrorDescriptor } from './errorMessages'

export type Health = {
  status: 'ok' | 'degraded'
  database: 'ok' | 'error'
  migration: string | null
}
export type HealthResult =
  | { kind: 'ok'; health: Health }
  | { kind: 'degraded'; health: Health }
  | { kind: 'error'; error: ErrorDescriptor }

function isHealth(value: unknown): value is Health {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (v.status === 'ok' || v.status === 'degraded') &&
    (v.database === 'ok' || v.database === 'error') &&
    (typeof v.migration === 'string' || v.migration === null)
}

// Both generations of the degraded 503 body are valid. Shared request() handles all
// other failures, preserving cancellation and the same code contract as protected APIs.
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResult> {
  try {
    const response = await request('/api/health', { signal }, [503])
    let body: unknown
    try { body = await response.json() } catch (error) {
      if (signal?.aborted || isAbortError(error)) throw error
      throw new ApiError('Invalid response body', response.status, 'INVALID_RESPONSE')
    }
    if (!isHealth(body)) throw new ApiError('Invalid response body', response.status, 'INVALID_RESPONSE')
    return body.status === 'ok' && response.status === 200
      ? { kind: 'ok', health: body } : { kind: 'degraded', health: body }
  } catch (error) {
    if (signal?.aborted || isAbortError(error)) throw error
    return { kind: 'error', error: describeError(error)! }
  }
}
