// Mirrors HealthResponse in backend/app/api/health.py (GET /api/health).
export type Health = {
  status: 'ok' | 'degraded'
  database: 'ok' | 'error'
  migration: string | null
}

export type HealthResult =
  | { kind: 'ok'; health: Health }
  | { kind: 'degraded'; health: Health }
  | { kind: 'error'; message: string }

function isHealth(value: unknown): value is Health {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    (v.status === 'ok' || v.status === 'degraded') &&
    (v.database === 'ok' || v.database === 'error') &&
    (typeof v.migration === 'string' || v.migration === null)
  )
}

// The backend answers 200 when healthy and 503 (with the same body) when the
// database is unreachable; anything else, including a network failure, is an error.
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResult> {
  let response: Response
  try {
    response = await fetch('/api/health', { signal })
  } catch (error) {
    if (signal?.aborted) throw error
    return { kind: 'error', message: 'API unreachable' }
  }

  if (response.status !== 200 && response.status !== 503) {
    return { kind: 'error', message: `Unexpected response: HTTP ${response.status}` }
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    return { kind: 'error', message: 'Invalid response body' }
  }
  if (!isHealth(body)) {
    return { kind: 'error', message: 'Invalid response body' }
  }
  return body.status === 'ok' && response.status === 200
    ? { kind: 'ok', health: body }
    : { kind: 'degraded', health: body }
}
