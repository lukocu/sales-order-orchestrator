import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Analysis, ChecksView, ParsedFields, RunSummary } from '../api/analysis'
import type { User } from '../api/auth'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'
import {
  ACME_APPROVED,
  ACME_DRAFT,
  ACME_REJECTED_EARLIER,
  DELTA_AWAITING,
  DELTA_SUBMITTED,
} from '../test/replyDraftFixtures'
import { SALES, SUPERVISOR } from '../test/userFixtures'
import AnalysisPanel from './AnalysisPanel'

type Handler = () => Response | Promise<Response>
type Routes = Record<string, Handler | Handler[]>

const PATH = '/api/inquiries/7/analysis'
const CHECKS_PATH = '/api/inquiries/7/checks'
const ORCHESTRATION_PATH = '/api/inquiries/7/orchestration'
const DECISION_PATH = '/api/inquiries/7/draft/decision'
const SUPERVISOR_DECISION_PATH = '/api/inquiries/7/draft/supervisor-decision'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Routes are keyed "METHOD /path"; an array answers with its items in order (the
// last one repeats).
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

const FIELDS: ParsedFields = {
  customer: 'ACME Sp. z o.o.',
  product_code: 'ABC-100',
  quantity: 80,
  deadline: '2026-11-06',
  deadline_text: 'do piątku',
  substitute_allowed: true,
  price_kind: 'best_price',
  price_value: null,
  price_text: 'najlepsza cena',
}

const LLM_RUN: RunSummary = {
  id: 3,
  status: 'completed',
  started_at: '2026-11-10T09:00:00Z',
  duration_ms: 1520.4,
  steps: [
    {
      id: 10,
      name: 'parse',
      kind: 'llm',
      status: 'ok',
      error_type: null,
      provider: 'groq',
      model: 'openai/gpt-oss-120b',
      input_tokens: 1200,
      output_tokens: 300,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_usd: '0.0003600000',
      price_status: 'priced',
      price_source: 'genai-prices 0.2.1',
      started_at: '2026-11-10T09:00:00Z',
      duration_ms: 1500.2,
    },
    {
      id: 11,
      name: 'resolve-deadline',
      kind: 'deterministic',
      status: 'ok',
      error_type: null,
      provider: null,
      model: null,
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_usd: null,
      price_status: 'not_applicable',
      price_source: null,
      started_at: '2026-11-10T09:00:01Z',
      duration_ms: 0.4,
    },
  ],
  totals: {
    input_tokens: 1200,
    output_tokens: 300,
    cache_read_tokens: 0,
    cost_usd: '0.0003600000',
    cost_complete: true,
    steps_duration_ms: 1500.6,
    duration_ms: 1520.4,
  },
}

const CHECKS_RUN: RunSummary = {
  ...LLM_RUN,
  id: 4,
  duration_ms: 3.1,
  steps: [{ ...LLM_RUN.steps[1], id: 20, name: 'classify' }],
  totals: {
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: '0',
    cost_complete: true,
    steps_duration_ms: 0.4,
    duration_ms: 3.1,
  },
}

// ACME asks for 80 × ABC-100 with 50 in stock.
const EXCEPTION: ChecksView = {
  outcome: 'exception',
  exception_type: 'insufficient_stock',
  reasons: [],
  results: {
    customer: { status: 'matched', matched_by: 'name', customer_id: 1, name: 'ACME', candidates: [] },
    stock: {
      status: 'insufficient',
      product_code: 'ABC-100',
      product_name: 'Czujnik ciśnienia ABC-100',
      requested: 80,
      available: 50,
      shortage: 30,
    },
    price: {
      status: 'ok',
      list_price: '120.00',
      discount_percent: '5.00',
      unit_price: '114.00',
      total: '9120.00',
      currency: 'PLN',
    },
    discount: {
      status: 'ok',
      standard_percent: '5.00',
      requested_kind: 'best_price',
      requested_value: null,
    },
    credit: { status: 'ok', limit: '30000.00', balance: '2000.00', order_value: '9120.00' },
    reasons: [],
  },
  checked_at: '2026-11-10T09:00:02Z',
  stale: false,
  uncertain_inputs: [],
  run: CHECKS_RUN,
}

// The same inquiry corrected to 20 pieces.
const STANDARD: ChecksView = {
  ...EXCEPTION,
  outcome: 'standard',
  exception_type: null,
  results: {
    ...EXCEPTION.results,
    stock: { ...EXCEPTION.results.stock, status: 'ok', requested: 20, shortage: 0 },
  },
}

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    inquiry_id: 7,
    extractor: 'groq',
    reference_date: '2026-11-02',
    fields: FIELDS,
    model_fields: FIELDS,
    uncertain: {},
    corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01.123456Z',
    analyzed_by_name: 'Anna Nowak',
    corrected_at: null,
    corrected_by_name: null,
    run: LLM_RUN,
    checks: null,
    orchestration: null,
    ...overrides,
  }
}

function renderPanel(
  onUnauthorized = vi.fn(),
  onOutcome = vi.fn(),
  { user = SALES, onDraftStatus = vi.fn() }: { user?: User; onDraftStatus?: () => void } = {},
) {
  render(
    <AnalysisPanel
      inquiryId={7}
      user={user}
      onUnauthorized={onUnauthorized}
      onOutcome={onOutcome}
      onDraftStatus={onDraftStatus}
    />,
  )
  return onUnauthorized
}

function putBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
  return JSON.parse(String(call?.[1]?.body))
}

describe('AnalysisPanel', () => {
  it('analyzes an inquiry without a result and shows the fields', async () => {
    let answer: (response: Response) => void = () => {}
    stubApi({
      [`GET ${PATH}`]: () => json(200, null),
      [`POST ${PATH}`]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Analyze request' }))

    expect(await screen.findByRole('button', { name: 'Analyzing…' })).toBeDisabled()
    answer(json(200, analysis()))

    expect(await screen.findByLabelText('Customer')).toHaveValue('ACME Sp. z o.o.')
    expect(screen.getByLabelText('Product')).toHaveValue('ABC-100')
    expect(screen.getByLabelText('Quantity')).toHaveValue('80')
    expect(screen.getByLabelText('Deadline')).toHaveValue('2026-11-06')
    expect(screen.getByText('“do piątku”')).toBeInTheDocument()
    expect(screen.getByLabelText('Substitute allowed')).toHaveValue('yes')
    expect(screen.getByLabelText('Price expectation')).toHaveValue('best_price')
    expect(screen.getByRole('button', { name: 'Save corrections' })).toBeDisabled()
  })

  it('flags an uncertain field with its reason', async () => {
    stubApi({
      [`GET ${PATH}`]: () =>
        json(200, analysis({ uncertain: { deadline: 'No deadline in the text' } })),
    })

    renderPanel()

    expect(await screen.findByText('Uncertain: No deadline in the text')).toBeInTheDocument()
    expect(screen.getByLabelText('Looks right')).not.toBeChecked()
  })

  it('saves fields, reviewed fields and analyzed_at', async () => {
    const corrected = analysis({
      fields: { ...FIELDS, quantity: 90 },
      corrected_fields: ['quantity'],
      corrected_at: '2026-11-10T09:05:00Z',
      corrected_by_name: 'Anna Nowak',
    })
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () =>
        json(200, analysis({ uncertain: { customer: 'Model: company name unclear' } })),
      [`PUT ${PATH}`]: () => json(200, corrected),
    })

    renderPanel()
    fireEvent.change(await screen.findByLabelText('Quantity'), { target: { value: '90' } })
    fireEvent.click(screen.getByLabelText('Looks right'))
    fireEvent.click(screen.getByRole('button', { name: 'Save corrections' }))

    expect(await screen.findByText('Corrections saved')).toBeInTheDocument()
    expect(putBody(fetchMock)).toEqual({
      fields: { ...FIELDS, quantity: 90 },
      reviewed: ['customer'],
      analyzed_at: '2026-11-10T09:00:01.123456Z',
    })
    expect(screen.getByText('edited · model: 80')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toHaveValue('90')
  })

  it('shows a validation error from the API at the form', async () => {
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis()),
      [`PUT ${PATH}`]: () =>
        json(422, {
          detail: [
            {
              loc: ['body', 'fields', 'quantity'],
              msg: 'Input should be greater than or equal to 1',
            },
          ],
        }),
    })

    renderPanel()
    fireEvent.change(await screen.findByLabelText('Quantity'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save corrections' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Input should be greater than or equal to 1',
    )
  })

  it('reloads the analysis when it changed since it was opened (409)', async () => {
    const fetchMock = stubApi({
      [`GET ${PATH}`]: [
        () => json(200, analysis()),
        () => json(200, analysis({ fields: { ...FIELDS, customer: 'ACME SA' } })),
      ],
      [`PUT ${PATH}`]: () => json(409, { detail: 'Analysis changed, reload' }),
    })

    renderPanel()
    fireEvent.change(await screen.findByLabelText('Customer'), { target: { value: 'Other' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save corrections' }))

    expect(
      await screen.findByText(/reloaded, your unsaved edits were discarded/),
    ).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.getByLabelText('Customer')).toHaveValue('ACME SA'))
    const reads = fetchMock.mock.calls.filter(([, init]) => (init?.method ?? 'GET') === 'GET')
    expect(reads).toHaveLength(2)
  })

  it('asks for confirmation before re-analyzing a corrected result', async () => {
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () =>
        json(
          200,
          analysis({
            fields: { ...FIELDS, quantity: 90 },
            corrected_fields: ['quantity'],
            corrected_at: '2026-11-10T09:05:00Z',
          }),
        ),
      [`POST ${PATH}`]: () => json(200, analysis()),
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Re-analyze' }))

    expect(screen.getByText('Corrections will be lost.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'Re-analyze anyway' }))

    await vi.waitFor(() => expect(screen.getByLabelText('Quantity')).toHaveValue('80'))
    expect(screen.queryByText('Corrections will be lost.')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })

  it('asks again before retrying a failed re-analysis of a corrected result', async () => {
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () =>
        json(
          200,
          analysis({
            fields: { ...FIELDS, quantity: 90 },
            corrected_fields: ['quantity'],
            corrected_at: '2026-11-10T09:05:00Z',
          }),
        ),
      [`POST ${PATH}`]: [
        () => json(502, { detail: 'Analysis failed, try again' }),
        () => json(200, analysis()),
      ],
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Re-analyze' }))
    fireEvent.click(screen.getByRole('button', { name: 'Re-analyze anyway' }))

    const alert = await screen.findByRole('alert')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(screen.getByText('Corrections will be lost.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })

  it.each([
    [502, 'Analysis failed, try again'],
    [503, 'LLM rate limit reached, try again later'],
  ])('shows the API message when analysis fails with %i', async (status, detail) => {
    stubApi({
      [`GET ${PATH}`]: () => json(200, null),
      [`POST ${PATH}`]: [() => json(status, { detail }), () => json(200, analysis())],
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Analyze request' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(detail)
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByLabelText('Customer')).toHaveValue('ACME Sp. z o.o.')
  })

  it('shows step metrics with list cost and unpriced steps', async () => {
    const unpricedStep = {
      ...LLM_RUN.steps[0],
      id: 12,
      name: 'parse-retry',
      model: 'gpt-oss-120b',
      cost_usd: null,
      price_status: 'unpriced' as const,
    }
    stubApi({
      [`GET ${PATH}`]: () =>
        json(
          200,
          analysis({
            run: {
              ...LLM_RUN,
              steps: [...LLM_RUN.steps, unpricedStep],
              totals: { ...LLM_RUN.totals, cost_complete: false },
            },
          }),
        ),
    })

    renderPanel()

    const metrics = await screen.findByRole('region', { name: 'Metrics' })
    const [parse, resolve, retry, total] = within(metrics).getAllByRole('listitem')
    expect(parse).toHaveTextContent('openai/gpt-oss-120b')
    expect(parse).toHaveTextContent('1200 in / 300 out')
    expect(parse).toHaveTextContent('$0.00036 list price')
    expect(parse).toHaveTextContent('1500 ms')
    expect(resolve).toHaveTextContent('deterministic')
    expect(resolve).toHaveTextContent('—')
    expect(retry).toHaveTextContent('not priced')
    expect(total).toHaveTextContent('$0.00036 list price (some steps not priced)')
    expect(screen.queryByText('Rule-based demo parser (no LLM)')).not.toBeInTheDocument()
  })

  it('marks the rule-based parser and a missing run', async () => {
    stubApi({ [`GET ${PATH}`]: () => json(200, analysis({ extractor: 'fake', run: null })) })

    renderPanel()

    expect(await screen.findByText('Rule-based demo parser (no LLM)')).toBeInTheDocument()
    expect(screen.getByText('Metrics unavailable')).toBeInTheDocument()
  })

  it('shows the checks below the analysis and reports the outcome after a correction', async () => {
    const onOutcome = vi.fn()
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis({ checks: EXCEPTION })),
      [`PUT ${PATH}`]: () =>
        json(
          200,
          analysis({
            fields: { ...FIELDS, quantity: 20 },
            corrected_fields: ['quantity'],
            corrected_at: '2026-11-10T09:05:00Z',
            checks: STANDARD,
          }),
        ),
    })

    renderPanel(vi.fn(), onOutcome)

    expect(await screen.findByText(/^Exception: insufficient stock/)).toBeInTheDocument()
    expect(onOutcome).toHaveBeenLastCalledWith(7, 'exception')

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save corrections' }))

    expect(
      await screen.findByText('Standard inquiry — completed without agents'),
    ).toBeInTheDocument()
    expect(onOutcome).toHaveBeenLastCalledWith(7, 'standard')
    // Two runs on one panel: the analysis and the checks have their own metrics.
    expect(screen.getByRole('region', { name: 'Metrics' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Checks metrics' })).toBeInTheDocument()
  })

  it('re-runs stale checks without discarding unsaved edits', async () => {
    const onOutcome = vi.fn()
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () => json(200, analysis({ checks: { ...EXCEPTION, stale: true } })),
      [`POST ${CHECKS_PATH}`]: () => json(200, analysis({ checks: EXCEPTION })),
    })

    renderPanel(vi.fn(), onOutcome)
    fireEvent.change(await screen.findByLabelText('Customer'), { target: { value: 'ACME SA' } })
    expect(onOutcome).toHaveBeenLastCalledWith(7, null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    await vi.waitFor(() => expect(onOutcome).toHaveBeenLastCalledWith(7, 'exception'))
    expect(screen.queryByRole('button', { name: 'Re-run checks' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Customer')).toHaveValue('ACME SA')
    expect(fetchMock).toHaveBeenCalledWith(CHECKS_PATH, expect.objectContaining({ method: 'POST' }))
  })

  it('disables saving and re-analyzing while the checks re-run', async () => {
    let answer: (response: Response) => void = () => {}
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis({ checks: { ...EXCEPTION, stale: true } })),
      [`POST ${CHECKS_PATH}`]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderPanel()
    fireEvent.change(await screen.findByLabelText('Customer'), { target: { value: 'ACME SA' } })
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    expect(await screen.findByRole('button', { name: 'Running checks…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save corrections' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeDisabled()
    answer(json(200, analysis({ checks: EXCEPTION })))

    expect(await screen.findByRole('button', { name: 'Save corrections' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Running checks…' })).not.toBeInTheDocument()
  })

  it('re-runs the orchestrator with every button disabled and keeps unsaved edits', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () =>
        json(
          200,
          analysis({
            checks: EXCEPTION,
            orchestration: {
              ...ACME_ORCHESTRATION,
              status: 'failed',
              tasks: [],
              error: { kind: 'planner_failed', code: 'unavailable', message: 'Planner unavailable' },
            },
          }),
        ),
      [`POST ${ORCHESTRATION_PATH}`]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderPanel()
    fireEvent.change(await screen.findByLabelText('Customer'), { target: { value: 'ACME SA' } })
    fireEvent.click(screen.getByRole('button', { name: 'Re-run orchestrator' }))

    expect(await screen.findByRole('button', { name: 'Running orchestrator…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save corrections' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith(
      ORCHESTRATION_PATH,
      expect.objectContaining({ method: 'POST' }),
    )
    answer(json(200, analysis({ checks: EXCEPTION, orchestration: ACME_ORCHESTRATION })))

    expect(await screen.findByText('Orchestration: Completed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeEnabled()
    expect(screen.getByLabelText('Customer')).toHaveValue('ACME SA')
    expect(screen.getByRole('region', { name: 'Orchestration metrics' })).toBeInTheDocument()
  })

  it('shows a failed orchestrator re-run with retry', async () => {
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis({ checks: EXCEPTION })),
      [`POST ${ORCHESTRATION_PATH}`]: [
        () => json(503, { detail: 'Database unavailable' }),
        () => json(200, analysis({ checks: EXCEPTION, orchestration: ACME_ORCHESTRATION })),
      ],
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Re-run orchestrator' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Re-running the orchestrator failed: Database unavailable')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Orchestration: Completed')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // ACME with its exception carried through to a reply draft.
  const DRAFTED: Partial<Analysis> = {
    checks: EXCEPTION,
    orchestration: ACME_ORCHESTRATION,
    recommendation: ACME_RECOMMENDATION,
    policy: ACME_POLICY,
    draft: ACME_DRAFT,
    decisions: [],
  }

  it('approves the reply draft with every button disabled meanwhile', async () => {
    let answer: (response: Response) => void = () => {}
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis(DRAFTED)),
      [`POST ${DECISION_PATH}`]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByRole('button', { name: 'Saving…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeDisabled()
    answer(
      json(
        200,
        analysis({
          ...DRAFTED,
          draft: { ...ACME_DRAFT, status: 'ready_to_send' },
          decisions: [ACME_APPROVED],
        }),
      ),
    )

    // The draft's status and its decision in the history.
    expect(await screen.findAllByText('Ready to send (sending is simulated)')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeEnabled()
    expect(screen.getByRole('region', { name: 'Decision history' })).toHaveTextContent(
      'Anna Kowalska',
    )
  })

  it('reloads the analysis when the draft changed since it was opened (409)', async () => {
    const fetchMock = stubApi({
      [`GET ${PATH}`]: [
        () => json(200, analysis(DRAFTED)),
        () =>
          json(
            200,
            analysis({
              ...DRAFTED,
              draft: { ...ACME_DRAFT, status: 'rejected' },
              decisions: [{ ...ACME_REJECTED_EARLIER, current: true }],
            }),
          ),
      ],
      [`POST ${DECISION_PATH}`]: () => json(409, { detail: 'Draft changed, reload' }),
    })

    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'The draft changed since it was opened — reloaded, your decision was not saved.',
    )
    expect(await screen.findByRole('button', { name: 'Regenerate draft' })).toBeEnabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([path]) => path === PATH)).toHaveLength(2)
  })

  it('keeps the decision history visible after a correction removes the exception', async () => {
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis({ ...DRAFTED, decisions: [ACME_APPROVED] })),
      [`PUT ${PATH}`]: () =>
        json(
          200,
          analysis({
            fields: { ...FIELDS, quantity: 20 },
            corrected_fields: ['quantity'],
            corrected_at: '2026-11-10T09:30:00Z',
            checks: STANDARD,
            orchestration: null,
            recommendation: null,
            policy: null,
            draft: null,
            decisions: [{ ...ACME_APPROVED, current: false }],
          }),
        ),
    })

    renderPanel()
    expect(await screen.findByRole('region', { name: 'Reply draft' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save corrections' }))

    expect(
      await screen.findByText('Standard inquiry — completed without agents'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Reply draft' })).not.toBeInTheDocument()
    const history = screen.getByRole('region', { name: 'Decision history' })
    expect(history).toHaveTextContent('Approved')
    expect(history).toHaveTextContent('earlier version')
  })

  it('shows no decision history without decisions', async () => {
    stubApi({ [`GET ${PATH}`]: () => json(200, analysis(DRAFTED)) })

    renderPanel()

    expect(await screen.findByRole('region', { name: 'Reply draft' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Decision history' })).not.toBeInTheDocument()
  })

  // Delta passed to the supervisor by the salesperson.
  const AWAITING: Partial<Analysis> = {
    ...DRAFTED,
    draft: DELTA_AWAITING,
    decisions: [DELTA_SUBMITTED],
  }

  it("approves as the supervisor with a reason and reports the draft's status", async () => {
    const onDraftStatus = vi.fn()
    const fetchMock = stubApi({
      [`GET ${PATH}`]: () => json(200, analysis(AWAITING)),
      [`POST ${SUPERVISOR_DECISION_PATH}`]: () =>
        json(
          200,
          analysis({
            ...AWAITING,
            draft: { ...DELTA_AWAITING, status: 'ready_to_send', submitted_by: null },
            decisions: [
              DELTA_SUBMITTED,
              {
                ...DELTA_SUBMITTED,
                action: 'supervisor_approve',
                status_after: 'ready_to_send',
                reason: 'Klient strategiczny',
                decided_by_name: 'Piotr Nowak',
              },
            ],
          }),
        ),
    })

    renderPanel(vi.fn(), vi.fn(), { user: SUPERVISOR, onDraftStatus })
    const group = await screen.findByRole('group', { name: 'Supervisor decision' })
    await vi.waitFor(() =>
      expect(onDraftStatus).toHaveBeenLastCalledWith(7, 'awaiting_supervisor'),
    )
    fireEvent.click(within(group).getByRole('button', { name: 'Approve' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Klient strategiczny' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findAllByText('Ready to send (sending is simulated)')).toHaveLength(2)
    expect(screen.getByRole('region', { name: 'Decision history' })).toHaveTextContent(
      'Approved by supervisor',
    )
    expect(onDraftStatus).toHaveBeenLastCalledWith(7, 'ready_to_send')
    const call = fetchMock.mock.calls.find(([path]) => path === SUPERVISOR_DECISION_PATH)
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      updated_at: DELTA_AWAITING.updated_at,
      action: 'approve',
      reason: 'Klient strategiczny',
    })
  })

  it("reloads the analysis when the draft changed before the supervisor's decision", async () => {
    const fetchMock = stubApi({
      [`GET ${PATH}`]: [
        () => json(200, analysis(AWAITING)),
        () => json(200, analysis({ ...AWAITING, draft: { ...DELTA_AWAITING, status: 'rejected' } })),
      ],
      [`POST ${SUPERVISOR_DECISION_PATH}`]: () => json(409, { detail: 'Draft changed, reload' }),
    })

    renderPanel(vi.fn(), vi.fn(), { user: SUPERVISOR })
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Marża za niska' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'The draft changed since it was opened — reloaded, your decision was not saved.',
    )
    expect(await screen.findByRole('button', { name: 'Regenerate draft' })).toBeEnabled()
    expect(fetchMock.mock.calls.filter(([path]) => path === PATH)).toHaveLength(2)
  })

  it("calls onUnauthorized when the supervisor's decision answers 401", async () => {
    stubApi({
      [`GET ${PATH}`]: () => json(200, analysis(AWAITING)),
      [`POST ${SUPERVISOR_DECISION_PATH}`]: () => json(401, { detail: 'Not authenticated' }),
    })

    const onUnauthorized = renderPanel(vi.fn(), vi.fn(), { user: SUPERVISOR })
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Nie' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })

  it('shows the salesperson no supervisor actions on a submitted draft', async () => {
    stubApi({ [`GET ${PATH}`]: () => json(200, analysis(AWAITING)) })

    renderPanel()

    expect(await screen.findByText('Waiting for a supervisor decision.')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Supervisor decision' })).not.toBeInTheDocument()
  })

  it('calls onUnauthorized when the API answers 401', async () => {
    stubApi({ [`GET ${PATH}`]: () => json(401, { detail: 'Not authenticated' }) })

    const onUnauthorized = renderPanel()

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
