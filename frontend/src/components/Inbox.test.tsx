import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Analysis, ChecksView, ParsedFields } from '../api/analysis'
import type { User } from '../api/auth'
import type { InquiryDetail, InquirySummary } from '../api/inquiries'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { DELTA_POLICY } from '../test/policyFixtures'
import { DELTA_RECOMMENDATION } from '../test/recommendationFixtures'
import { DELTA_AWAITING, DELTA_SUBMITTED } from '../test/replyDraftFixtures'
import { SALES, SUPERVISOR } from '../test/userFixtures'
import Inbox from './Inbox'

type Handler = () => Response
type Routes = Record<string, Handler | Handler[]>

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Routes are keyed "METHOD /path"; an array answers with its items in order (the last one
// repeats).
function stubApi(routes: Routes) {
  const queues = new Map(Object.entries(routes))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const route = queues.get(key)
    if (route === undefined) throw new Error(`Unexpected request: ${key}`)
    if (Array.isArray(route)) {
      const handler = route.length > 1 ? route.shift()! : route[0]
      return handler()
    }
    return route()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// Hurtownia Delta, passed to the supervisor by the salesperson.
const DELTA: InquiryDetail = {
  id: 3,
  sender_name: 'Hurtownia Delta',
  sender_email: 'zakupy@delta.example.com',
  subject: 'Zamówienie ABC-100',
  received_at: '2026-11-09T11:00:00Z',
  outcome: 'exception',
  draft_status: 'awaiting_supervisor',
  body: 'Prosimy o 500 szt. ABC-100.',
}

const ACME: InquirySummary = {
  id: 2,
  sender_name: 'ACME Sp. z o.o.',
  sender_email: 'zakupy@acme.example.com',
  subject: 'Zapytanie ofertowe ABC-100',
  received_at: '2026-11-09T10:00:00Z',
  outcome: 'exception',
  draft_status: 'draft',
}

const OMEGA: InquirySummary = {
  id: 1,
  sender_name: 'Omega',
  sender_email: 'biuro@omega.example.com',
  subject: 'Tonery do drukarek',
  received_at: '2026-11-08T09:00:00Z',
  outcome: null,
  draft_status: null,
}

const { body: _body, ...DELTA_SUMMARY } = DELTA

const SUMMARIES: InquirySummary[] = [DELTA_SUMMARY, ACME, OMEGA]

const FIELDS: ParsedFields = {
  customer: 'Hurtownia Delta',
  product_code: 'ABC-100',
  quantity: 500,
  deadline: null,
  deadline_text: null,
  substitute_allowed: true,
  price_kind: 'none',
  price_value: null,
  price_text: null,
}

const EXCEPTION: ChecksView = {
  outcome: 'exception',
  exception_type: 'insufficient_stock',
  reasons: [],
  results: {
    customer: {
      status: 'matched',
      matched_by: 'email',
      customer_id: 3,
      name: 'Hurtownia Delta',
      candidates: [],
    },
    stock: {
      status: 'insufficient',
      product_code: 'ABC-100',
      product_name: 'Czujnik ciśnienia ABC-100',
      requested: 500,
      available: 50,
      shortage: 450,
    },
    price: {
      status: 'ok',
      list_price: '120.00',
      discount_percent: '0.00',
      unit_price: '120.00',
      total: '60000.00',
      currency: 'PLN',
    },
    discount: {
      status: 'ok',
      standard_percent: '0.00',
      requested_kind: 'none',
      requested_value: null,
    },
    credit: { status: 'ok', limit: '100000.00', balance: '0.00', order_value: '60000.00' },
    reasons: [],
  },
  checked_at: '2026-11-10T09:00:02Z',
  stale: false,
  uncertain_inputs: [],
  run: null,
}

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    inquiry_id: DELTA.id,
    extractor: 'fake',
    reference_date: '2026-11-02',
    fields: FIELDS,
    model_fields: FIELDS,
    uncertain: {},
    corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01Z',
    analyzed_by_name: 'Anna Kowalska',
    corrected_at: null,
    corrected_by_name: null,
    run: null,
    checks: EXCEPTION,
    orchestration: ACME_ORCHESTRATION,
    recommendation: DELTA_RECOMMENDATION,
    policy: DELTA_POLICY,
    draft: DELTA_AWAITING,
    decisions: [DELTA_SUBMITTED],
    ...overrides,
  }
}

function renderInbox(user: User) {
  const onSignedOut = vi.fn()
  render(<Inbox user={user} onSignedOut={onSignedOut} />)
  return onSignedOut
}

function listedSubjects(): string[] {
  const list = within(screen.getByRole('region', { name: 'Inbox' })).queryByRole('list')
  if (list === null) return []
  return within(list)
    .getAllByRole('listitem')
    .map((item) => item.querySelector('.inquiry__subject')?.textContent ?? '')
}

function filterButton(): HTMLElement {
  return screen.getByRole('button', { name: /^Awaiting supervisor only/ })
}

describe('Inbox', () => {
  it('marks an inquiry awaiting the supervisor with a badge', async () => {
    stubApi({ 'GET /api/inquiries': () => json(200, SUMMARIES) })

    renderInbox(SALES)

    const delta = await screen.findByRole('button', { name: /Zamówienie ABC-100/ })
    expect(within(delta).getByText('Awaiting supervisor')).toHaveClass(
      'badge',
      'badge--awaiting_supervisor',
    )
    expect(within(delta).getByText('Exception')).toBeInTheDocument()
    const acme = screen.getByRole('button', { name: /Zapytanie ofertowe ABC-100/ })
    expect(within(acme).queryByText('Awaiting supervisor')).not.toBeInTheDocument()
  })

  it.each([
    ['salesperson', SALES],
    ['supervisor', SUPERVISOR],
  ])('lets a %s filter to the inquiries awaiting the supervisor', async (_, user) => {
    stubApi({ 'GET /api/inquiries': () => json(200, SUMMARIES) })

    renderInbox(user)

    await screen.findByRole('button', { name: /Zamówienie ABC-100/ })
    expect(filterButton()).toHaveAttribute('aria-pressed', 'false')
    expect(filterButton()).toHaveTextContent('Awaiting supervisor only (1)')
    expect(listedSubjects()).toHaveLength(3)

    fireEvent.click(filterButton())

    expect(filterButton()).toHaveAttribute('aria-pressed', 'true')
    expect(listedSubjects()).toEqual(['Zamówienie ABC-100'])

    fireEvent.click(filterButton())

    expect(filterButton()).toHaveAttribute('aria-pressed', 'false')
    expect(listedSubjects()).toHaveLength(3)
  })

  it('says when no inquiry awaits the supervisor', async () => {
    stubApi({ 'GET /api/inquiries': () => json(200, [ACME, OMEGA]) })

    renderInbox(SUPERVISOR)

    await screen.findByRole('button', { name: /Zapytanie ofertowe ABC-100/ })
    expect(filterButton()).toHaveTextContent('Awaiting supervisor only (0)')
    fireEvent.click(filterButton())

    expect(screen.getByText('No inquiries awaiting a supervisor.')).toBeInTheDocument()
    expect(listedSubjects()).toEqual([])
  })

  it("removes the badge and updates the count after the supervisor's decision", async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, analysis()),
      'POST /api/inquiries/3/draft/supervisor-decision': () =>
        json(
          200,
          analysis({
            draft: { ...DELTA_AWAITING, status: 'rejected', submitted_by: null },
            decisions: [
              DELTA_SUBMITTED,
              {
                ...DELTA_SUBMITTED,
                action: 'supervisor_reject',
                status_after: 'rejected',
                reason: 'Marża za niska',
                decided_by_name: SUPERVISOR.display_name,
              },
            ],
          }),
        ),
    })

    renderInbox(SUPERVISOR)
    fireEvent.click(await screen.findByRole('button', { name: /Zamówienie ABC-100/ }))
    fireEvent.click(filterButton())

    const group = await screen.findByRole('group', { name: 'Supervisor decision' })
    fireEvent.click(within(group).getByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Marża za niska' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(
      await screen.findByRole('region', { name: 'Decision history' }),
    ).toHaveTextContent('Rejected by supervisor')
    await vi.waitFor(() =>
      expect(filterButton()).toHaveTextContent('Awaiting supervisor only (0)'),
    )
    expect(listedSubjects()).toEqual([])
    fireEvent.click(filterButton())
    const delta = screen.getByRole('button', { name: /Zamówienie ABC-100/ })
    expect(within(delta).queryByText('Awaiting supervisor')).not.toBeInTheDocument()
  })
})
