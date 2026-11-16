import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import i18n from './i18n'
import type { Analysis, ChecksView } from './api/analysis'
import type { User } from './api/auth'
import type { InquiryDetail } from './api/inquiries'
import { renderWithRouter } from './test/renderWithRouter'

type Handler = () => Response
type Routes = Record<string, Handler | Handler[]>

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const HEALTH: Handler = () =>
  json(200, { status: 'ok', database: 'ok', migration: '0003_users_inquiries' })
const UNAUTHORIZED: Handler = () => json(401, { detail: 'Not authenticated' })

const SALES: User = { id: 1, username: 'sales', display_name: 'Anna Nowak', role: 'salesperson' }

const NEWER: InquiryDetail = {
  id: 2,
  sender_name: 'Jan Kowalski',
  sender_email: 'jan@example.com',
  subject: 'Zapytanie o papier A4',
  received_at: '2026-11-09T10:00:00Z',
  source: 'sample',
  outcome: 'exception',
  draft_status: null,
  body: 'Dzień dobry,\nproszę o wycenę 2 palet papieru A4.',
}
const OLDER: InquiryDetail = {
  id: 1,
  sender_name: 'Ewa Zielińska',
  sender_email: 'ewa@example.com',
  subject: 'Tonery do drukarek',
  received_at: '2026-11-08T09:00:00Z',
  source: 'sample',
  outcome: null,
  draft_status: null,
  body: 'Prosimy o ofertę na tonery.',
}

// A standard result for OLDER: customer, product and quantity found, enough in stock.
const STANDARD: ChecksView = {
  outcome: 'standard',
  exception_type: null,
  reasons: [],
  results: {
    customer: { status: 'matched', matched_by: 'email', customer_id: 2, name: 'Biuro Max', candidates: [] },
    stock: {
      status: 'ok',
      product_code: 'ABC-200',
      product_name: 'Moduł sterujący ABC-200',
      requested: 20,
      available: 150,
      shortage: 0,
    },
    price: {
      status: 'ok',
      list_price: '85.00',
      discount_percent: '0.00',
      unit_price: '85.00',
      total: '1700.00',
      currency: 'PLN',
    },
    discount: { status: 'ok', standard_percent: '0.00', requested_kind: 'none', requested_value: null },
    credit: { status: 'ok', limit: '10000.00', balance: '0.00', order_value: '1700.00' },
    reasons: [],
  },
  checked_at: '2026-11-10T09:00:02Z',
  stale: false,
  uncertain_inputs: [],
  run: null,
}

const OLDER_ANALYSIS: Analysis = {
  inquiry_id: 1,
  extractor: 'fake',
  reference_date: '2026-11-08',
  fields: {
    customer: null,
    product_code: 'ABC-200',
    quantity: 20,
    deadline: null,
    deadline_text: null,
    substitute_allowed: null,
    price_kind: 'none',
    price_value: null,
    price_text: null,
  },
  model_fields: {
    customer: null,
    product_code: 'ABC-200',
    quantity: 20,
    deadline: null,
    deadline_text: null,
    substitute_allowed: null,
    price_kind: 'none',
    price_value: null,
    price_text: null,
  },
  uncertain: {},
  corrected_fields: [],
  analyzed_at: '2026-11-10T09:00:01Z',
  analyzed_by_name: 'Anna Nowak',
  corrected_at: null,
  corrected_by_name: null,
  run: null,
  checks: STANDARD,
  orchestration: null,
}

function summary({ body: _body, ...rest }: InquiryDetail) {
  return rest
}

// Routes are keyed "METHOD /path"; an array answers with its items in order (the
// last one repeats). Health is always answered so the footer has data.
function stubApi(routes: Routes) {
  const queues = new Map(Object.entries(routes))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key === 'GET /api/health') return HEALTH()
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

const SIGNED_IN_INBOX: Routes = {
  'GET /api/auth/me': () => json(200, SALES),
  'GET /api/inquiries': () => json(200, [summary(NEWER), summary(OLDER)]),
  'GET /api/inquiries/2': () => json(200, NEWER),
  'GET /api/inquiries/1': () => json(200, OLDER),
  'GET /api/inquiries/2/analysis': () => json(200, null),
  'GET /api/inquiries/1/analysis': () => json(200, null),
  'POST /api/auth/logout': () => new Response(null, { status: 204 }),
}

function signIn(username: string, password: string) {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: username } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('App', () => {
  it('shows the sign-in form when there is no session', async () => {
    stubApi({ 'GET /api/auth/me': UNAUTHORIZED })

    await renderWithRouter('/')

    expect(screen.getByRole('heading', { name: 'Sales Order Orchestrator' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('signs in and shows the inbox newest first', async () => {
    const fetchMock = stubApi({
      ...SIGNED_IN_INBOX,
      'GET /api/auth/me': UNAUTHORIZED,
      'POST /api/auth/login': () => json(200, SALES),
    })

    await renderWithRouter('/')
    await screen.findByRole('heading', { name: 'Sign in' })
    signIn('sales', 'demo')

    expect(await screen.findByText('Anna Nowak')).toBeInTheDocument()
    expect(screen.getByText('Salesperson')).toBeInTheDocument()
    const items = await screen.findAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText('Zapytanie o papier A4')).toBeInTheDocument()
    expect(within(items[0]).getByText('Jan Kowalski')).toBeInTheDocument()
    expect(within(items[1]).getByText('Tonery do drukarek')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'sales', password: 'demo' }),
      }),
    )
  })

  it('shows the body of a clicked inquiry', async () => {
    stubApi(SIGNED_IN_INBOX)

    await renderWithRouter('/')
    fireEvent.click(await screen.findByRole('link', { name: /Zapytanie o papier A4/ }))

    expect(await screen.findByText(/proszę o wycenę 2 palet papieru A4/)).toBeInTheDocument()
    expect(screen.getByText(/jan@example\.com/)).toBeInTheDocument()
  })

  it('returns to the sign-in form after Sign out', async () => {
    const fetchMock = stubApi(SIGNED_IN_INBOX)

    await renderWithRouter('/')
    fireEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/logout',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows the Sign out error under the header and stays signed in', async () => {
    stubApi({
      ...SIGNED_IN_INBOX,
      'POST /api/auth/logout': () => json(500, { detail: 'Logout failed' }),
    })

    await renderWithRouter('/')
    fireEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Logout failed')
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeEnabled()
    expect(screen.getByText('Anna Nowak')).toBeInTheDocument()
  })

  it('returns to the sign-in form when the inbox answers 401', async () => {
    stubApi({ ...SIGNED_IN_INBOX, 'GET /api/inquiries': UNAUTHORIZED })

    await renderWithRouter('/')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('returns to the sign-in form when an inquiry answers 401', async () => {
    stubApi({ ...SIGNED_IN_INBOX, 'GET /api/inquiries/2': UNAUTHORIZED })

    await renderWithRouter('/')
    fireEvent.click(await screen.findByRole('link', { name: /Zapytanie o papier A4/ }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('shows the outcome badge of each inquiry and updates it after an analysis', async () => {
    const fetchMock = stubApi({
      ...SIGNED_IN_INBOX,
      'POST /api/inquiries/1/analysis': () => json(200, OLDER_ANALYSIS),
    })

    await renderWithRouter('/')
    const newer = await screen.findByRole('link', { name: /Zapytanie o papier A4/ })
    const older = screen.getByRole('link', { name: /Tonery do drukarek/ })
    expect(within(newer).getByText('Exception')).toBeInTheDocument()
    expect(older.querySelector('[data-slot="badge"]')).toBeNull()

    fireEvent.click(older)
    fireEvent.click(await screen.findByRole('button', { name: 'Analyze request' }))

    expect(await within(older).findByText('Standard')).toBeInTheDocument()
    expect(within(newer).getByText('Exception')).toBeInTheDocument()
    const listReads = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/inquiries')
    expect(listReads).toHaveLength(1)
  })

  it('shows a message for an empty inbox', async () => {
    stubApi({ ...SIGNED_IN_INBOX, 'GET /api/inquiries': () => json(200, []) })

    await renderWithRouter('/')

    expect(await screen.findByText('No inquiries yet.')).toBeInTheDocument()
  })

  it('shows an error with retry when the session check fails', async () => {
    stubApi({
      'GET /api/auth/me': [() => json(503, { detail: 'Database unavailable' }), UNAUTHORIZED],
    })

    await renderWithRouter('/')

    expect(await screen.findByText(/Database unavailable/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('shows the health footer when signed in', async () => {
    stubApi(SIGNED_IN_INBOX)

    await renderWithRouter('/')

    expect(await screen.findByText('All systems operational')).toBeInTheDocument()
    expect(screen.getByText('0003_users_inquiries')).toBeInTheDocument()
  })

  it('hides the health footer on the sign-in screen', async () => {
    const fetchMock = stubApi({ 'GET /api/auth/me': UNAUTHORIZED })

    await renderWithRouter('/')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'System status' })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('opens in Polish when Polish is chosen', async () => {
    await i18n.changeLanguage('pl')
    stubApi({ 'GET /api/auth/me': UNAUTHORIZED })

    await renderWithRouter('/')

    expect(await screen.findByRole('button', { name: 'Zaloguj się' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('pl')
  })

  describe('routing', () => {
    it('opens the inquiry named in the address', async () => {
      stubApi(SIGNED_IN_INBOX)

      const router = await renderWithRouter('/inquiries/1')

      expect(await screen.findByText('Prosimy o ofertę na tonery.')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Tonery do drukarek/ })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(router.state.location.pathname).toBe('/inquiries/1')
    })

    it('moves to the address of a clicked inquiry', async () => {
      stubApi(SIGNED_IN_INBOX)

      const router = await renderWithRouter('/')
      fireEvent.click(await screen.findByRole('link', { name: /Tonery do drukarek/ }))

      await waitFor(() => expect(router.state.location.pathname).toBe('/inquiries/1'))
      expect(await screen.findByText('Prosimy o ofertę na tonery.')).toBeInTheDocument()
    })

    it('shows not-found for an unknown address', async () => {
      stubApi(SIGNED_IN_INBOX)

      await renderWithRouter('/nope')

      expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Back to the inbox' })).toHaveAttribute('href', '/')
      expect(screen.queryByRole('region', { name: 'Inbox' })).not.toBeInTheDocument()
    })

    it.each(['abc', '0', '-1', '1.5'])(
      'shows not-found for the inquiry id "%s" without asking the API',
      async (id) => {
        const fetchMock = stubApi(SIGNED_IN_INBOX)

        await renderWithRouter(`/inquiries/${id}`)

        expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
        const inquiryReads = fetchMock.mock.calls.filter(([input]) =>
          String(input).startsWith('/api/inquiries'),
        )
        expect(inquiryReads).toHaveLength(0)
      },
    )

    it('shows sign-in at an inquiry address, keeps it, and opens the inquiry after sign-in', async () => {
      stubApi({
        ...SIGNED_IN_INBOX,
        'GET /api/auth/me': UNAUTHORIZED,
        'POST /api/auth/login': () => json(200, SALES),
      })

      const router = await renderWithRouter('/inquiries/1')

      expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/inquiries/1')
      expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument()

      signIn('sales', 'demo')

      expect(await screen.findByText('Prosimy o ofertę na tonery.')).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/inquiries/1')
    })

    it('marks the current page in the navigation', async () => {
      stubApi(SIGNED_IN_INBOX)

      const router = await renderWithRouter('/inquiries/1')
      const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
      const inbox = within(nav).getByRole('link', { name: 'Inbox' })
      const system = within(nav).getByRole('link', { name: 'System' })
      expect(inbox).toHaveAttribute('aria-current', 'page')
      expect(system).not.toHaveAttribute('aria-current')

      fireEvent.click(system)

      await waitFor(() => expect(router.state.location.pathname).toBe('/system'))
      expect(system).toHaveAttribute('aria-current', 'page')
      expect(inbox).not.toHaveAttribute('aria-current')

      fireEvent.click(inbox)

      await waitFor(() => expect(router.state.location.pathname).toBe('/'))
      expect(inbox).toHaveAttribute('aria-current', 'page')
      expect(system).not.toHaveAttribute('aria-current')
    })
  })
})
