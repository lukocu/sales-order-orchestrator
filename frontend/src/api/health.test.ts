import { expect, it, vi } from 'vitest'
import { fetchHealth } from './health'

it.each([false, true])('accepts degraded health with code=%s', async (coded) => {
  const health = { status: 'degraded', database: 'error', migration: null }
  const body = coded ? { ...health, detail: 'Database unavailable', code: 'DATABASE_UNAVAILABLE' } : health
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 503 })))
  await expect(fetchHealth()).resolves.toEqual({ kind: 'degraded', health: body })
})
it('returns a descriptor for network failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('private')))
  await expect(fetchHealth()).resolves.toMatchObject({ kind: 'error', error: { code: 'NETWORK_ERROR' } })
})
it('returns a descriptor for an unexpected response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{bad')))
  await expect(fetchHealth()).resolves.toMatchObject({ kind: 'error', error: { code: 'INVALID_RESPONSE' } })
})
it('preserves cancelled health requests', async () => {
  const error = new DOMException('Cancelled', 'AbortError')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error))
  await expect(fetchHealth()).rejects.toBe(error)
})
