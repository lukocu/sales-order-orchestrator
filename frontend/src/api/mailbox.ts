import { requestJson } from './client'

// Mirrors FetchResult in backend/app/mailbox/service.py (POST /api/mailbox/fetch).
export type FetchResult = {
  fetched: number // messages read from the mailbox
  created: number // new inquiries
  duplicates: number // already in the inbox
  skipped: number // could not be turned into an inquiry
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isFetchResult(value: unknown): value is FetchResult {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return isCount(v.fetched) && isCount(v.created) && isCount(v.duplicates) && isCount(v.skipped)
}

// POST /api/mailbox/fetch: stores the newest mailbox messages that are not inquiries yet.
// Failures → ApiError with the server's detail (503 not configured, 502 mailbox
// failure, 409 a fetch already running); 401 → UnauthorizedError.
export function fetchMail(): Promise<FetchResult> {
  return requestJson('/api/mailbox/fetch', isFetchResult, { method: 'POST' })
}
