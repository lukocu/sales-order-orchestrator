import { act, fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Analysis, ChecksView, ParsedFields } from '../api/analysis'
import type { User } from '../api/auth'
import type { InquiryDetail, InquirySummary } from '../api/inquiries'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { DELTA_POLICY } from '../test/policyFixtures'
import { DELTA_RECOMMENDATION } from '../test/recommendationFixtures'
import { DELTA_AWAITING, DELTA_SUBMITTED } from '../test/replyDraftFixtures'
import { renderWithRouter } from '../test/renderWithRouter'
import { SALES, SUPERVISOR } from '../test/userFixtures'
import i18n from '@/i18n'

type Handler = () => Response | Promise<Response>
type Routes = Record<string, Handler | Handler[]>

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// The inbox renders inside the signed-in app; `renderInbox` picks who is signed in.
let signedIn: User = SALES

// Routes are keyed "METHOD /path"; an array answers with its items in order (the last one
// repeats). The session and the health footer are always answered.
function stubApi(routes: Routes) {
  const queues = new Map(Object.entries(routes))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key === 'GET /api/auth/me') return json(200, signedIn)
    if (key === 'GET /api/health') {
      return json(200, { status: 'ok', database: 'ok', migration: '0012' })
    }
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
  source: 'sample',
  outcome: 'exception',
  draft_status: 'awaiting_supervisor',
  analyzed: true,
  body: 'Prosimy o 500 szt. ABC-100.',
}

const ACME: InquirySummary = {
  id: 2,
  sender_name: 'ACME Sp. z o.o.',
  sender_email: 'zakupy@acme.example.com',
  subject: 'Zapytanie ofertowe ABC-100',
  received_at: '2026-11-09T10:00:00Z',
  source: 'sample',
  outcome: 'exception',
  draft_status: 'draft',
  analyzed: true,
}

const OMEGA: InquirySummary = {
  id: 1,
  sender_name: 'Omega',
  sender_email: 'biuro@omega.example.com',
  subject: 'Tonery do drukarek',
  received_at: '2026-11-08T09:00:00Z',
  source: 'sample',
  outcome: null,
  draft_status: null,
  analyzed: false,
}

const { body: _body, ...DELTA_SUMMARY } = DELTA

const SUMMARIES: InquirySummary[] = [DELTA_SUMMARY, ACME, OMEGA]

// An inquiry stored from the test mailbox.
const MAILED: InquirySummary = {
  id: 4,
  sender_name: 'Biuro Max',
  sender_email: 'biuro@max.example.com',
  subject: 'Zapytanie z poczty',
  received_at: '2026-11-10T08:00:00Z',
  source: 'mailbox',
  outcome: null,
  draft_status: null,
  analyzed: false,
}

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

// Renders the app at `path` (the inbox lives on `/` and `/inquiries/$inquiryId`).
function renderInbox(user: User, path = '/') {
  signedIn = user
  return renderWithRouter(path)
}

function listedSubjects(): string[] {
  const list = within(screen.getByRole('region', { name: 'Inbox' })).queryByRole('list')
  if (list === null) return []
  return within(list)
    .getAllByRole('listitem')
    .map((item) => item.querySelector('[data-field="subject"]')?.textContent ?? '')
}

function fetchButton(): HTMLElement {
  return screen.getByRole('button', { name: /^(Fetch mail|Fetching…)$/ })
}

// The status badge of a row: every row has exactly one, next to the optional mailbox badge.
function statusBadge(row: HTMLElement): HTMLElement {
  const badges = Array.from(row.querySelectorAll<HTMLElement>('[data-slot="badge"]')).filter(
    (badge) => badge.textContent?.startsWith('Status:'),
  )
  expect(badges).toHaveLength(1)
  return badges[0]
}

// The status badge in the header of the open inquiry.
function headerBadge(): HTMLElement {
  const badge = screen
    .getByRole('region', { name: 'Inquiry' })
    .querySelector<HTMLElement>('article [data-slot="badge"]')
  expect(badge).not.toBeNull()
  return badge!
}

function filterButton(): HTMLElement {
  return screen.getByRole('button', { name: /^Awaiting supervisor only/ })
}

describe('Inbox', () => {
  it('shows one status badge per row, for each of the seven statuses', async () => {
    const row = (id: number, subject: string, fields: Partial<InquirySummary>): InquirySummary => ({
      ...OMEGA,
      id,
      subject,
      ...fields,
    })
    stubApi({
      'GET /api/inquiries': () =>
        json(200, [
          row(11, 'S new', {}),
          row(12, 'S analysed', { analyzed: true }),
          row(13, 'S exception', { analyzed: true, outcome: 'exception', draft_status: 'draft' }),
          row(14, 'S needs input', { analyzed: true, outcome: 'needs_input' }),
          row(15, 'S awaiting', {
            analyzed: true,
            outcome: 'exception',
            draft_status: 'awaiting_supervisor',
          }),
          row(16, 'S ready', { analyzed: true, outcome: 'exception', draft_status: 'ready_to_send' }),
          row(17, 'S rejected', { analyzed: true, outcome: 'exception', draft_status: 'rejected' }),
        ]),
    })

    await renderInbox(SALES)

    await screen.findByRole('link', { name: /S new/ })
    const expected: [string, string, string][] = [
      ['S new', 'New', 'outline'],
      ['S analysed', 'Analysed', 'success-outline'],
      ['S exception', 'Exception', 'destructive-outline'],
      ['S needs input', 'Needs input', 'warning-outline'],
      ['S awaiting', 'Awaiting supervisor', 'warning'],
      ['S ready', 'Ready to send', 'success'],
      ['S rejected', 'Rejected', 'destructive-outline'],
    ]
    for (const [subject, text, variant] of expected) {
      const badge = statusBadge(screen.getByRole('link', { name: new RegExp(subject) }))
      expect(badge).toHaveTextContent(`Status: ${text}`)
      expect(badge).toHaveAttribute('data-variant', variant)
    }
  })

  it('shows the status of an inquiry awaiting the supervisor once, next to the mailbox badge', async () => {
    stubApi({ 'GET /api/inquiries': () => json(200, [{ ...DELTA_SUMMARY, source: 'mailbox' }, ACME]) })

    await renderInbox(SALES)

    const delta = await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    expect(statusBadge(delta)).toHaveTextContent('Status: Awaiting supervisor')
    expect(within(delta).getByText('E-mail')).toBeInTheDocument()
    expect(within(delta).queryByText('Exception')).not.toBeInTheDocument()
    const acme = screen.getByRole('link', { name: /Zapytanie ofertowe ABC-100/ })
    expect(statusBadge(acme)).toHaveTextContent('Status: Exception')
  })

  it('shows the same status in the header of the open inquiry as in its row', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, analysis()),
    })

    await renderInbox(SUPERVISOR, '/inquiries/3')

    const row = await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    await screen.findByRole('group', { name: 'Supervisor decision' })
    expect(headerBadge()).toHaveTextContent('Status: Awaiting supervisor')
    expect(headerBadge()).toHaveAttribute('data-variant', statusBadge(row).dataset.variant)
  })

  it("falls back to the detail's own status in the header when the list failed", async () => {
    stubApi({
      'GET /api/inquiries': () => json(500, { detail: 'Database unavailable' }),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, analysis()),
    })

    await renderInbox(SUPERVISOR, '/inquiries/3')

    await screen.findByRole('group', { name: 'Supervisor decision' })
    expect(headerBadge()).toHaveTextContent('Status: Awaiting supervisor')
  })

  it('updates the row and the header in place from the facts the panel reports', async () => {
    const fetchMock = stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/2': () => json(200, { ...ACME, body: 'Prosimy o ofertę.' }),
      'GET /api/inquiries/2/analysis': () =>
        json(
          200,
          analysis({
            inquiry_id: 2,
            draft: { ...DELTA_AWAITING, status: 'ready_to_send', submitted_by: null },
          }),
        ),
    })

    await renderInbox(SALES, '/inquiries/2')

    const row = await screen.findByRole('link', { name: /Zapytanie ofertowe ABC-100/ })
    await vi.waitFor(() => expect(statusBadge(row)).toHaveTextContent('Status: Ready to send'))
    expect(headerBadge()).toHaveTextContent('Status: Ready to send')
    const listReads = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/inquiries')
    expect(listReads).toHaveLength(1)
  })

  it.each([
    ['salesperson', SALES],
    ['supervisor', SUPERVISOR],
  ])('lets a %s filter to the inquiries awaiting the supervisor', async (_, user) => {
    stubApi({ 'GET /api/inquiries': () => json(200, SUMMARIES) })

    await renderInbox(user)

    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
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

    await renderInbox(SUPERVISOR)

    await screen.findByRole('link', { name: /Zapytanie ofertowe ABC-100/ })
    expect(filterButton()).toHaveTextContent('Awaiting supervisor only (0)')
    fireEvent.click(filterButton())

    expect(screen.getByText('No inquiries awaiting a supervisor.')).toBeInTheDocument()
    expect(listedSubjects()).toEqual([])
  })

  it('keeps an awaiting inquiry read-only in the supervisor ordinary view', async () => {
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

    await renderInbox(SUPERVISOR)
    fireEvent.click(await screen.findByRole('link', { name: /Zamówienie ABC-100/ }))
    fireEvent.click(filterButton())

    const group = await screen.findByRole('group', { name: 'Supervisor decision' })
    expect(within(group).getByRole('button', { name: 'Reject' })).toBeDisabled()
    expect(within(group).getByRole('button', { name: 'Approve' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'Open supervisor review' })).toHaveAttribute(
      'href',
      '/approvals/3',
    )
    fireEvent.click(within(group).getByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Marża za niska' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(
      await screen.findByRole('region', { name: 'Decision history' }),
    ).toHaveTextContent('Awaiting supervisor approval')
    await vi.waitFor(() =>
      expect(filterButton()).toHaveTextContent('Awaiting supervisor only (1)'),
    )
    expect(listedSubjects()).toHaveLength(1)
    fireEvent.click(filterButton())
    const delta = screen.getByRole('link', { name: /Zamówienie ABC-100/ })
    expect(statusBadge(delta)).toHaveTextContent('Status: Awaiting supervisor')
  })

  it('fetches mail, reloads the list and marks the inquiry from the mailbox', async () => {
    const fetchMock = stubApi({
      'GET /api/inquiries': [() => json(200, SUMMARIES), () => json(200, [MAILED, ...SUMMARIES])],
      'POST /api/mailbox/fetch': () =>
        json(200, { fetched: 5, created: 1, duplicates: 3, skipped: 1 }),
    })

    await renderInbox(SALES)
    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    expect(screen.queryByText('E-mail')).not.toBeInTheDocument()

    fireEvent.click(fetchButton())

    const mailed = await screen.findByRole('link', { name: /Zapytanie z poczty/ })
    expect(within(mailed).getByText('E-mail')).toHaveAttribute('data-variant', 'outline')
    const acme = screen.getByRole('link', { name: /Zapytanie ofertowe ABC-100/ })
    expect(within(acme).queryByText('E-mail')).not.toBeInTheDocument()
    expect(screen.getByText('1 new, 3 already in inbox, 1 skipped')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/mailbox/fetch',
      expect.objectContaining({ method: 'POST' }),
    )
    const listReads = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/inquiries')
    expect(listReads).toHaveLength(2)
  })

  it('says when the mailbox has no new mail', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'POST /api/mailbox/fetch': () =>
        json(200, { fetched: 3, created: 0, duplicates: 3, skipped: 0 }),
    })

    await renderInbox(SALES)
    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    fireEvent.click(fetchButton())

    expect(await screen.findByText('No new mail')).toBeInTheDocument()
  })

  it('translates the fetch summary again after a language switch', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'POST /api/mailbox/fetch': () =>
        json(200, { fetched: 3, created: 0, duplicates: 3, skipped: 0 }),
    })

    await renderInbox(SALES)
    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    fireEvent.click(fetchButton())
    await screen.findByText('No new mail')

    await act(() => i18n.changeLanguage('pl'))

    expect(screen.getByText('Brak nowej poczty')).toBeInTheDocument()
    expect(screen.queryByText('No new mail')).not.toBeInTheDocument()
  })

  it('says when the mailbox is not configured', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'POST /api/mailbox/fetch': () => json(503, { detail: 'Mailbox not configured' }),
    })

    await renderInbox(SALES)
    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    fireEvent.click(fetchButton())

    expect(await screen.findByText('An administrator needs to set up this feature. Contact them to continue.')).toHaveClass('text-destructive')
    expect(listedSubjects()).toHaveLength(3)
  })

  it('disables the button while the fetch runs', async () => {
    let answer: (response: Response) => void = () => {}
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'POST /api/mailbox/fetch': () =>
        new Promise<Response>((resolve) => {
          answer = resolve
        }),
    })

    await renderInbox(SALES)
    await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    fireEvent.click(fetchButton())

    expect(fetchButton()).toBeDisabled()
    expect(fetchButton()).toHaveTextContent('Fetching…')

    answer(json(200, { fetched: 0, created: 0, duplicates: 0, skipped: 0 }))

    expect(await screen.findByText('No new mail')).toBeInTheDocument()
    expect(fetchButton()).toBeEnabled()
    expect(fetchButton()).toHaveTextContent('Fetch mail')
  })

  it("opens a clicked inquiry at its address and keeps the list", async () => {
    const fetchMock = stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, null),
    })

    const router = await renderInbox(SALES)
    const delta = await screen.findByRole('link', { name: /Zamówienie ABC-100/ })
    expect(delta).toHaveAttribute('href', '/inquiries/3')
    expect(delta).not.toHaveAttribute('aria-current')

    fireEvent.click(delta)

    expect(await screen.findByText('Prosimy o 500 szt. ABC-100.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/inquiries/3')
    expect(screen.getByRole('link', { name: /Zamówienie ABC-100/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: /Zapytanie ofertowe ABC-100/ })).not.toHaveAttribute(
      'aria-current',
    )
    const listReads = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/inquiries')
    expect(listReads).toHaveLength(1)
  })

  it('opens the inquiry named in the address', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, null),
    })

    await renderInbox(SUPERVISOR, '/inquiries/3')

    expect(await screen.findByText('Prosimy o 500 szt. ABC-100.')).toBeInTheDocument()
    expect(
      await screen.findByRole('link', { name: /Zamówienie ABC-100/ }),
    ).toHaveAttribute('aria-current', 'page')
  })

  it('keeps the e-mail in the inquiry step and the detail area out of a live region', async () => {
    stubApi({
      'GET /api/inquiries': () => json(200, SUMMARIES),
      'GET /api/inquiries/3': () => json(200, DELTA),
      'GET /api/inquiries/3/analysis': () => json(200, null),
    })

    await renderInbox(SUPERVISOR, '/inquiries/3')

    const detail = await screen.findByRole('region', { name: 'Inquiry' })
    const body = await within(detail).findByText('Prosimy o 500 szt. ABC-100.')
    expect(detail).not.toHaveAttribute('aria-live')
    expect(within(detail).getByRole('heading', { name: 'Zamówienie ABC-100' })).toBeInTheDocument()
    expect(within(detail).getByRole('tabpanel')).toContainElement(body)
    expect(within(detail).getAllByText('Prosimy o 500 szt. ABC-100.')).toHaveLength(1)
  })
})
