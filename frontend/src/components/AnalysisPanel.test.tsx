import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Analysis, ParsedFields, RunSummary } from '../api/analysis'
import AnalysisPanel from './AnalysisPanel'

type Handler = () => Response | Promise<Response>
type Routes = Record<string, Handler | Handler[]>

const PATH = '/api/inquiries/7/analysis'

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
    ...overrides,
  }
}

function renderPanel(onUnauthorized = vi.fn()) {
  render(<AnalysisPanel inquiryId={7} onUnauthorized={onUnauthorized} />)
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

  it('calls onUnauthorized when the API answers 401', async () => {
    stubApi({ [`GET ${PATH}`]: () => json(401, { detail: 'Not authenticated' }) })

    const onUnauthorized = renderPanel()

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
