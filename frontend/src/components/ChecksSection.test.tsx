import { fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type {
  Analysis,
  ChecksView,
  ParsedFields,
  RunSummary,
  StepSummary,
} from '../api/analysis'
import ChecksSection from './ChecksSection'

const CHECKS_PATH = '/api/inquiries/7/checks'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(...responses: (() => Response)[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key !== `POST ${CHECKS_PATH}`) throw new Error(`Unexpected request: ${key}`)
    const handler = responses.length > 1 ? responses.shift()! : responses[0]
    return handler()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const FIELDS: ParsedFields = {
  customer: 'ACME Sp. z o.o.',
  product_code: 'ABC-100',
  quantity: 80,
  deadline: null,
  deadline_text: null,
  substitute_allowed: true,
  price_kind: 'best_price',
  price_value: null,
  price_text: 'najlepsza cena',
}

const STEP_NAMES = [
  'match-customer',
  'check-stock',
  'check-price',
  'check-discount',
  'check-credit',
  'classify',
]

function step(name: string, index: number): StepSummary {
  return {
    id: 20 + index,
    name,
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
    started_at: '2026-11-10T09:00:02Z',
    duration_ms: 0.3,
  }
}

const CHECKS_RUN: RunSummary = {
  id: 4,
  status: 'completed',
  started_at: '2026-11-10T09:00:02Z',
  duration_ms: 4.2,
  steps: STEP_NAMES.map(step),
  totals: {
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: '0',
    cost_complete: true,
    steps_duration_ms: 1.8,
    duration_ms: 4.2,
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

// ACME asks for 20 × ABC-100: enough in stock.
const STANDARD: ChecksView = {
  ...EXCEPTION,
  outcome: 'standard',
  exception_type: null,
  results: {
    ...EXCEPTION.results,
    stock: { ...EXCEPTION.results.stock, status: 'ok', requested: 20, shortage: 0 },
  },
}

// Neither the customer nor the product is in the records.
const NEEDS_INPUT: ChecksView = {
  ...EXCEPTION,
  outcome: 'needs_input',
  exception_type: null,
  reasons: ['customer_not_found', 'product_not_found'],
  results: {
    customer: { status: 'not_found', matched_by: null, customer_id: null, name: null, candidates: [] },
    stock: {
      status: 'skipped',
      product_code: 'QQQ-1',
      product_name: null,
      requested: 80,
      available: null,
      shortage: null,
    },
    price: {
      status: 'skipped',
      list_price: null,
      discount_percent: null,
      unit_price: null,
      total: null,
      currency: 'PLN',
    },
    discount: {
      status: 'skipped',
      standard_percent: null,
      requested_kind: 'best_price',
      requested_value: null,
    },
    credit: { status: 'skipped', limit: null, balance: null, order_value: null },
    reasons: ['customer_not_found', 'product_not_found'],
  },
}

function analysis(checks: ChecksView | null, fields: Partial<ParsedFields> = {}): Analysis {
  return {
    inquiry_id: 7,
    extractor: 'fake',
    reference_date: '2026-11-02',
    fields: { ...FIELDS, ...fields },
    model_fields: FIELDS,
    uncertain: {},
    corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01Z',
    analyzed_by_name: 'Anna Nowak',
    corrected_at: null,
    corrected_by_name: null,
    run: null,
    checks,
  }
}

// Holds the analysis like AnalysisPanel does, so a re-run result is shown.
function Harness({ initial, onUnauthorized }: { initial: Analysis; onUnauthorized: () => void }) {
  const [current, setCurrent] = useState(initial)
  return (
    <ChecksSection
      inquiryId={7}
      analysis={current}
      disabled={false}
      onRerun={setCurrent}
      onUnauthorized={onUnauthorized}
    />
  )
}

function renderSection(initial: Analysis, onUnauthorized = vi.fn()) {
  render(<Harness initial={initial} onUnauthorized={onUnauthorized} />)
  return onUnauthorized
}

function checkItem(name: string): HTMLElement {
  const list = screen.getByRole('list', { name: 'Individual checks' })
  const item = within(list)
    .getAllByRole('listitem')
    .find((li) => li.querySelector('.check__name')?.textContent === name)
  if (item === undefined) throw new Error(`No check named ${name}`)
  return item
}

describe('ChecksSection', () => {
  it('shows a standard inquiry with the 0-token metrics of the checks run', () => {
    renderSection(analysis(STANDARD))

    const banner = screen.getByText('Standard inquiry — completed without agents').parentElement!
    expect(banner).toHaveTextContent('0 in / 0 out')
    expect(banner).toHaveTextContent('Cost—')
    expect(banner).toHaveTextContent('4.2 ms')
    expect(banner).toHaveTextContent('Steps6')
    expect(checkItem('Stock')).toHaveTextContent('In stock')
    expect(screen.getByRole('region', { name: 'Checks metrics' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run checks' })).not.toBeInTheDocument()
  })

  it('shows an insufficient-stock exception with the substitute consent', () => {
    renderSection(analysis(EXCEPTION))

    expect(
      screen.getByText('Exception: insufficient stock — requested 80, available 50 (short 30)'),
    ).toBeInTheDocument()
    expect(screen.getByText('Handed over to orchestration (not available yet)')).toBeInTheDocument()
    expect(screen.getByText('Substitute: the customer accepts one')).toBeInTheDocument()
    expect(checkItem('Customer')).toHaveTextContent('Matched')
    expect(checkItem('Customer')).toHaveTextContent('ACME')
    expect(checkItem('Customer')).toHaveTextContent('Matched byname')
    expect(checkItem('Stock')).toHaveTextContent('Insufficient')
    expect(checkItem('Stock')).toHaveTextContent('Short30')
    expect(checkItem('Price')).toHaveTextContent('Unit price114.00 PLN')
    expect(checkItem('Price')).toHaveTextContent('Discount5%')
    expect(checkItem('Price')).toHaveTextContent('Value9120.00 PLN')
    expect(checkItem('Credit')).toHaveTextContent('Within limit')
  })

  it('marks a discount above the standard and a credit over the limit', () => {
    const delta: ChecksView = {
      ...EXCEPTION,
      results: {
        ...EXCEPTION.results,
        discount: {
          status: 'above_standard',
          standard_percent: '10.00',
          requested_kind: 'discount_percent',
          requested_value: '25',
        },
        credit: {
          status: 'over_limit',
          limit: '50000.00',
          balance: '0.00',
          order_value: '54000.00',
        },
      },
    }
    renderSection(analysis(delta, { substitute_allowed: false }))

    expect(checkItem('Discount')).toHaveTextContent('Above standard')
    expect(checkItem('Discount')).toHaveTextContent('Standard10%')
    expect(checkItem('Discount')).toHaveTextContent('Requested25%')
    expect(checkItem('Credit')).toHaveTextContent('Over limit')
    expect(checkItem('Credit')).toHaveTextContent('Order value54000.00 PLN')
    expect(screen.getByText('Substitute: the customer does not accept one')).toBeInTheDocument()
  })

  it('lists the reasons of needs input and shows skipped checks as a dash', () => {
    renderSection(analysis(NEEDS_INPUT))

    expect(screen.getByText('Needs input')).toBeInTheDocument()
    expect(screen.getByText('Customer not found in records')).toBeInTheDocument()
    expect(screen.getByText('Product QQQ-1 not found in the catalogue')).toBeInTheDocument()
    expect(checkItem('Customer')).toHaveTextContent('Not found')
    for (const name of ['Stock', 'Price', 'Discount', 'Credit']) {
      expect(checkItem(name).querySelector('.check__status')).toHaveTextContent(/^—$/)
    }
  })

  it('warns when the checks used uncertain fields', () => {
    renderSection(analysis({ ...EXCEPTION, uncertain_inputs: ['customer', 'quantity'] }))

    expect(screen.getByText('Based on uncertain fields: Customer, Quantity')).toBeInTheDocument()
  })

  it('re-runs stale checks and shows the new result', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = vi.fn(
      async () => new Promise<Response>((resolve) => (answer = resolve)),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderSection(analysis({ ...EXCEPTION, stale: true }))

    expect(screen.getByText(/the result may be out of date/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    expect(await screen.findByRole('button', { name: 'Running checks…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith(CHECKS_PATH, expect.objectContaining({ method: 'POST' }))
    answer(json(200, analysis(STANDARD)))

    expect(
      await screen.findByText('Standard inquiry — completed without agents'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run checks' })).not.toBeInTheDocument()
  })

  it('offers to run the checks when an analysis has no result', async () => {
    stubFetch(() => json(200, analysis(EXCEPTION)))
    renderSection(analysis(null))

    expect(screen.getByText('No check result for this analysis yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    expect(await screen.findByText(/^Exception: insufficient stock/)).toBeInTheDocument()
  })

  it('shows a failed re-run as an alert with retry', async () => {
    const fetchMock = stubFetch(
      () => json(503, { detail: 'Database unavailable' }),
      () => json(200, analysis(STANDARD)),
    )
    renderSection(analysis({ ...EXCEPTION, stale: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Database unavailable')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(
      await screen.findByText('Standard inquiry — completed without agents'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('calls onUnauthorized when the re-run answers 401', async () => {
    stubFetch(() => json(401, { detail: 'Not authenticated' }))
    const onUnauthorized = renderSection(analysis(null))
    fireEvent.click(screen.getByRole('button', { name: 'Re-run checks' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
