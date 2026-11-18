import { describe, expect, it, vi } from 'vitest'
import { ApiError, request, requestJson, UnauthorizedError } from './client'
import { describeError, errorMessage } from './errorMessages'
import i18n from '../i18n'

function reply(body: unknown, status: number) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
const isNull = (body: unknown): body is null => body === null

describe('coded API failures', () => {
  it.each([
    [401, 'INVALID_CREDENTIALS'], [401, 'NOT_AUTHENTICATED'], [403, 'SUPERVISOR_REQUIRED'],
    [404, 'INQUIRY_NOT_FOUND'], [409, 'DRAFT_CHANGED'], [422, 'VALIDATION_ERROR'],
    [429, 'RATE_LIMITED'], [500, 'INTERNAL_ERROR'], [502, 'MAILBOX_UNAVAILABLE'],
    [503, 'DATABASE_UNAVAILABLE'],
  ])('preserves status %i and code %s with diagnostic detail', async (status, code) => {
    reply({ detail: 'private exception', code, params: { retry_after: 4, invalid: false, nested: {} } }, status)
    await expect(request('/api/test')).rejects.toMatchObject({
      status, code, message: 'private exception', params: { retry_after: 4 },
    })
  })

  it.each(['FUTURE_ERROR', 'toString', 'constructor', '__proto__'])('does not guess an unknown code %s from status or detail', async (code) => {
    reply({ detail: 'Invalid username or password', code }, 401)
    let failure: unknown
    try { await request('/api/test') } catch (error) { failure = error }
    expect(failure).toBeInstanceOf(UnauthorizedError)
    expect(errorMessage(failure, i18n.t, 'login')).toBe(i18n.t('apiErrors.generic'))
  })

  it.each([
    ['Draft changed, reload', 409, 'DRAFT_CHANGED'],
    ['Mailbox unavailable', 502, 'MAILBOX_UNAVAILABLE'],
    ['Invalid username or password', 401, 'INVALID_CREDENTIALS'],
    ['Not authenticated', 401, 'NOT_AUTHENTICATED'],
    ['Reason is required', 422, 'REASON_REQUIRED'],
  ])('supports the exact legacy detail %s', async (detail, status, code) => {
    reply({ detail }, status)
    await expect(request('/api/test')).rejects.toMatchObject({ status, code, message: detail })
    expect(new ApiError(detail, status).code).toBe(code)
  })

  it.each(['private Draft changed, reload extra', 'constructor', 'toString', '__proto__'])('does not recognize arbitrary legacy text %s', (message) => {
    expect(new ApiError(message).code).toBe('UNKNOWN_ERROR')
  })

  it('treats legacy validation arrays as a code without displaying validator text', async () => {
    reply({ detail: [{ msg: 'private validator message', input: 'private password' }] }, 422)
    let failure: unknown
    try { await request('/api/test') } catch (error) { failure = error }
    expect(failure).toMatchObject({ code: 'VALIDATION_ERROR', status: 422, message: 'private validator message' })
    expect(errorMessage(failure, i18n.t)).toBe(i18n.t('apiErrors.validation'))
    expect(errorMessage(failure, i18n.t)).not.toContain('private')
  })

  it.each([401, 403, 500])('handles malformed error JSON for status %i', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('bad json', { status })))
    const result = request('/api/test')
    await expect(result).rejects.toMatchObject({ status, code: 'INVALID_RESPONSE' })
    if (status === 401) await expect(result).rejects.toBeInstanceOf(UnauthorizedError)
  })

  it('wraps a network failure once and does not retry writes', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('private network details'))
    vi.stubGlobal('fetch', fetchMock)
    const result = request('/api/test', { method: 'POST' })
    await expect(result).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: null })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('preserves AbortError even without an explicit signal', async () => {
    const abort = new DOMException('Cancelled', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(request('/api/test')).rejects.toBe(abort)
    expect(describeError(abort)).toBeNull()
    expect(errorMessage(abort, i18n.t)).toBe('')
  })

  it('preserves cancellation while reading error JSON', async () => {
    const abort = new DOMException('Cancelled', 'AbortError')
    const response = new Response('{}', { status: 401 })
    vi.spyOn(response, 'json').mockRejectedValue(abort)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(request('/api/test')).rejects.toBe(abort)
  })

  it('preserves an aborted signal during error body parsing', async () => {
    const controller = new AbortController()
    const failure = new Error('Original cancellation failure')
    const response = new Response('{}', { status: 500 })
    vi.spyOn(response, 'json').mockImplementation(async () => { controller.abort(); throw failure })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(request('/api/test', { signal: controller.signal })).rejects.toBe(failure)
  })

  it('preserves cancellation while reading JSON', async () => {
    const abort = new DOMException('Cancelled', 'AbortError')
    const response = new Response('{}')
    vi.spyOn(response, 'json').mockRejectedValue(abort)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(requestJson('/api/test', isNull)).rejects.toBe(abort)
  })

  it('accepts null as a valid empty analysis', async () => {
    reply(null, 200)
    await expect(requestJson('/api/test', isNull)).resolves.toBeNull()
  })

  it.each(['{bad', '{}'])('identifies invalid successful response %s', async (body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
    await expect(requestJson('/api/test', isNull)).rejects.toMatchObject({ code: 'INVALID_RESPONSE', status: 200 })
  })
})
