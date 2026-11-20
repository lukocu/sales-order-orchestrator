import { act, fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Analysis } from '../api/analysis'
import type { SupervisorQueue as QueueData, SupervisorReview as ReviewData } from '../api/supervisor'
import { DELTA_AWAITING, DELTA_SUBMITTED } from '../test/replyDraftFixtures'
import { renderWithRouter } from '../test/renderWithRouter'
import { SALES, SUPERVISOR } from '../test/userFixtures'

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const queue: QueueData = {
  total: 1,
  items: [{
    id: 17,
    sender_name: 'Hurtownia Delta',
    subject: 'Zamówienie ABC-100',
    received_at: '2026-11-09T11:00:00Z',
    submitted_at: '2026-11-10T09:30:00Z',
    submitted_by: 2,
    draft_updated_at: DELTA_AWAITING.updated_at,
    attention_rules: [{ code: 'margin', verdict: 'fail' }],
    review_state: 'actionable',
  }],
}

function review(updatedAt = DELTA_AWAITING.updated_at): ReviewData {
  return {
    inquiry_id: 17,
    sender_name: 'Hurtownia Delta',
    sender_email: 'zakupy@delta.example.com',
    subject: 'Zamówienie ABC-100',
    body: 'Please quote 500 units.',
    received_at: '2026-11-09T11:00:00Z',
    draft_status: 'awaiting_supervisor',
    draft_updated_at: updatedAt,
    submitted_at: '2026-11-10T09:30:00Z',
    submitted_by: 2,
    review_state: 'actionable',
    allowed_actions: ['approve', 'reject'],
    offer: { ...DELTA_AWAITING.offer, edited: true },
    offer_unavailable: false,
    offer_subject: DELTA_AWAITING.subject,
    offer_body: DELTA_AWAITING.body,
    policy: DELTA_AWAITING.policy,
    context: { fields: null, checks: null, orchestration: null, recommendation: null, policy: DELTA_AWAITING.policy },
    decisions: [DELTA_SUBMITTED],
  }
}

let signedIn = SUPERVISOR
let queueCalls = 0
let reviewCalls = 0
let decisionCalls = 0
let reviewResponses: ReviewData[] = []
let queueFailsAfterInitial = false
let decisionStatus = 409
let reviewUnauthorized = false
let queuePending = false
let queueAbortOnUnmount = false
let queueAborted = false
let resolveFirstQueue: ((response: Response) => void) | null = null
let fetchMock: ReturnType<typeof vi.fn>

const emptyAnalysis: Analysis = {
  inquiry_id: 17,
  extractor: 'fake',
  reference_date: '2026-11-01',
  fields: { customer: null, product_code: null, quantity: null, deadline: null, deadline_text: null, substitute_allowed: null, price_kind: 'none', price_value: null, price_text: null },
  model_fields: { customer: null, product_code: null, quantity: null, deadline: null, deadline_text: null, substitute_allowed: null, price_kind: 'none', price_value: null, price_text: null },
  uncertain: {},
  corrected_fields: [],
  analyzed_at: '2026-11-01T00:00:00Z',
  analyzed_by_name: null,
  corrected_at: null,
  corrected_by_name: null,
  run: null,
  checks: null,
  orchestration: null,
}

beforeEach(() => {
  signedIn = SUPERVISOR
  queueCalls = 0
  reviewCalls = 0
  decisionCalls = 0
  reviewResponses = [review()]
  queueFailsAfterInitial = false
  decisionStatus = 409
  reviewUnauthorized = false
  queuePending = false
  queueAbortOnUnmount = false
  queueAborted = false
  resolveFirstQueue = null
  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    if (path === '/api/auth/me') return json(200, signedIn)
    if (path === '/api/health') return json(200, { status: 'ok', database: 'ok', migration: '0012' })
    if (path === '/api/auth/logout' && method === 'POST') return json(204)
    if (path === '/api/supervisor/queue') {
      queueCalls += 1
      if (queuePending && queueCalls === 1) {
        return new Promise<Response>((resolve) => { resolveFirstQueue = resolve })
      }
      if (queuePending && queueCalls > 1) return json(200, { items: [], total: 0 })
      if (queueAbortOnUnmount && queueCalls === 1) {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            queueAborted = init.signal?.aborted ?? false
            reject(new DOMException('Aborted', 'AbortError'))
          })
        })
      }
      if (queueFailsAfterInitial && queueCalls > 1) return json(500, { detail: 'Unavailable' })
      return json(200, decisionCalls > 0 && decisionStatus === 200 ? { items: [], total: 0 } : queue)
    }
    if (path === '/api/supervisor/reviews/17' && method === 'GET') {
      if (reviewUnauthorized) return json(401, { detail: 'Unauthorized' })
      const response = reviewResponses[Math.min(reviewCalls, reviewResponses.length - 1)]
      reviewCalls += 1
      return json(200, response)
    }
    if (path === '/api/inquiries/17/draft/supervisor-decision' && method === 'POST') {
      decisionCalls += 1
      return decisionStatus === 200 ? json(200, emptyAnalysis) : json(decisionStatus, { detail: 'Draft changed' })
    }
    throw new Error(`Unexpected request: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
})

describe('Supervisor queue and review routes', () => {
  it('shares one queue result between the navigation count and the list', async () => {
    await renderWithRouter('/approvals')

    expect(await screen.findByRole('link', { name: /Hurtownia Delta/ })).toHaveTextContent(
      'Waiting',
    )
    expect(screen.getByRole('link', { name: /To approve/ })).toHaveTextContent('1')
    expect(queueCalls).toBe(1)
  })

  it('does not fetch queue data for a salesperson opening a review URL directly', async () => {
    signedIn = SALES
    await renderWithRouter('/approvals/17')

    expect(await screen.findByText('Supervisor access required')).toBeInTheDocument()
    expect(queueCalls).toBe(0)
    expect(reviewCalls).toBe(0)
  })

  it('shows a salesperson the access message at the queue address without asking for the queue', async () => {
    signedIn = SALES
    const router = await renderWithRouter('/approvals')

    expect(await screen.findByText('Supervisor access required')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/approvals')
    expect(queueCalls).toBe(0)
  })

  it('allows rejection but hides approval for the supervisor’s own submission', async () => {
    reviewResponses = [{ ...review(), submitted_by: SUPERVISOR.id, allowed_actions: ['reject'] }]
    await renderWithRouter('/approvals/17')
    expect(await screen.findByRole('button', { name: 'Reject' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(screen.getByText('Edited offer')).toBeInTheDocument()
  })

  it('allows rejection but hides approval for a stale submission', async () => {
    reviewResponses = [{ ...review(), review_state: 'stale', allowed_actions: ['reject'] }]
    await renderWithRouter('/approvals/17')
    expect(await screen.findByText('Out of date')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })

  it('does not show a made-up offer when offer data is unavailable', async () => {
    reviewResponses = [{ ...review(), review_state: 'unavailable', allowed_actions: ['reject'], offer: null, offer_unavailable: true }]
    await renderWithRouter('/approvals/17')
    expect(await screen.findByText(/offer details are unavailable/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })

  it('keeps the requested URL while an anonymous user signs in', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === '/api/auth/me') return json(401, { detail: 'Unauthorized' })
      if (String(input) === '/api/health') return json(200, { status: 'ok', database: 'ok', migration: '0012' })
      throw new Error(`Unexpected request: ${String(input)}`)
    }))

    const router = await renderWithRouter('/approvals/17')

    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/approvals/17')
  })

  it('keeps the requested URL when a review request expires the session', async () => {
    reviewUnauthorized = true
    const router = await renderWithRouter('/approvals/17')

    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/approvals/17')
  })

  it('retains a stale count after refresh failure and lets the supervisor retry', async () => {
    queueFailsAfterInitial = true
    await renderWithRouter('/approvals')
    await screen.findByRole('link', { name: /Hurtownia Delta/ })

    fireEvent.click(screen.getByRole('button', { name: 'Refresh queue' }))

    expect((await screen.findAllByText(/Showing the last available count/)).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /To approve/ })).toHaveTextContent('1')
    expect(queueCalls).toBe(2)
  })

  it('refreshes the shared count when the tab becomes visible', async () => {
    await renderWithRouter('/approvals')
    await screen.findByRole('link', { name: /Hurtownia Delta/ })
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    fireEvent(document, new Event('visibilitychange'))
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    fireEvent(document, new Event('visibilitychange'))

    await vi.waitFor(() => expect(queueCalls).toBe(2))
  })

  it('ignores an older queue response after a newer refresh has completed', async () => {
    queuePending = true
    await renderWithRouter('/approvals')
    await vi.waitFor(() => expect(queueCalls).toBe(1))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh queue' }))
    expect(await screen.findByText('No inquiries are waiting for a decision.')).toBeInTheDocument()
    expect(queueCalls).toBe(2)

    await act(async () => {
      resolveFirstQueue?.(json(200, queue))
    })
    expect(screen.getByText('No inquiries are waiting for a decision.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /To approve/ })).toHaveTextContent('0')
  })

  it('cancels a pending queue request on logout', async () => {
    queueAbortOnUnmount = true
    await renderWithRouter('/approvals')
    await vi.waitFor(() => expect(queueCalls).toBe(1))
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(queueAborted).toBe(true)
  })

  it('requires a comment and refreshes a changed review after 409 without resending', async () => {
    reviewResponses = [review(), review('2026-11-10T10:00:00Z')]
    await renderWithRouter('/approvals/17')

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    expect(screen.getByRole('button', { name: 'Confirm approval' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Reviewed offer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByText(/This inquiry has changed. Refresh it and review the current details/)).toBeInTheDocument()
    expect(await screen.findByText(/Review the latest offer/)).toBeInTheDocument()
    expect(decisionCalls).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: 'I reviewed the latest inquiry' }))
    expect(screen.getByRole('button', { name: 'Confirm approval' })).toBeEnabled()
  })

  it('keeps a decision comment when a server response cannot confirm the write', async () => {
    decisionStatus = 500
    await renderWithRouter('/approvals/17')
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    const reason = screen.getByLabelText('Reason (required)')
    fireEvent.change(reason, { target: { value: 'Please check the margin.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The result of this action could not be confirmed. It may have been saved.')
    expect(reason).toHaveValue('Please check the margin.')
    expect(decisionCalls).toBe(1)
  })

  it('keeps the result visible after a successful decision and removes it from the shared queue', async () => {
    decisionStatus = 200
    reviewResponses = [review(), {
      ...review(),
      draft_status: 'ready_to_send',
      draft_updated_at: null,
      submitted_at: null,
      submitted_by: null,
      review_state: 'not_awaiting',
      allowed_actions: [],
    }]
    await renderWithRouter('/approvals/17')
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Approved.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByRole('status')).toHaveTextContent(/Decision complete: Ready to send/)
    expect(screen.getByRole('heading', { name: 'Zamówienie ABC-100' })).toHaveFocus()
    await vi.waitFor(() => expect(screen.getByRole('link', { name: /To approve/ })).toHaveTextContent('0'))
    expect(decisionCalls).toBe(1)
  })
})
