import { fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  rerunPolicy,
  type Analysis,
  type ParsedFields,
  type PolicyView,
  type RecommendationView,
} from '../api/analysis'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { ACME_POLICY, CREDIT_NOT_EVALUATED, DELTA_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION, DELTA_RECOMMENDATION } from '../test/recommendationFixtures'
import PolicySection from './PolicySection'

const POLICY_PATH = '/api/inquiries/7/policy'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(...responses: (() => Response)[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key !== `POST ${POLICY_PATH}`) throw new Error(`Unexpected request: ${key}`)
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
  deadline: '2026-11-06',
  deadline_text: 'do piątku',
  substitute_allowed: true,
  price_kind: 'best_price',
  price_value: null,
  price_text: 'najlepsza cena',
}

function analysis(policy: PolicyView | null): Analysis {
  return {
    inquiry_id: 7,
    extractor: 'fake',
    reference_date: '2026-11-02',
    fields: FIELDS,
    model_fields: FIELDS,
    uncertain: {},
    corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01Z',
    analyzed_by_name: 'Anna Nowak',
    corrected_at: null,
    corrected_by_name: null,
    run: null,
    checks: null,
    orchestration: ACME_ORCHESTRATION,
    recommendation: ACME_RECOMMENDATION,
    policy,
  }
}

// Holds the verdict and the re-run state like AnalysisPanel does.
function Harness({
  initial,
  recommendation,
  onUnauthorized,
}: {
  initial: PolicyView | null
  recommendation: RecommendationView | null
  onUnauthorized: () => void
}) {
  const [current, setCurrent] = useState(initial)
  const [running, setRunning] = useState(false)

  async function rerun() {
    setRunning(true)
    try {
      setCurrent((await rerunPolicy(7)).policy ?? null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <PolicySection
      inquiryId={7}
      policy={current}
      recommendation={recommendation}
      disabled={running}
      running={running}
      onRerun={rerun}
      onUnauthorized={onUnauthorized}
    />
  )
}

function renderSection(
  initial: PolicyView | null,
  recommendation: RecommendationView | null = ACME_RECOMMENDATION,
  onUnauthorized = vi.fn(),
) {
  render(
    <Harness initial={initial} recommendation={recommendation} onUnauthorized={onUnauthorized} />,
  )
  return onUnauthorized
}

// Cell texts of each body row: rule, actual, threshold, verdict, reason.
function rows(): string[][] {
  const table = screen.getByRole('table', { name: 'Policy rules' })
  const [, ...body] = within(table).getAllByRole('row')
  return body.map((row) =>
    Array.from(row.querySelectorAll('th, td')).map((cell) => cell.textContent ?? ''),
  )
}

describe('PolicySection', () => {
  it('shows ACME as needing no approval with every rule passing', () => {
    renderSection(ACME_POLICY)

    expect(screen.getByText('No approval needed')).toBeInTheDocument()
    expect(screen.getByText(/option stock\+ABC-110$/)).toBeInTheDocument()
    expect(rows()).toEqual([
      ['Margin', '25.51%', '≥ 20%', 'Pass', 'Margin at or above the minimum'],
      ['Discount', '5%', '≤ 15%', 'Pass', 'Standard discount within the maximum'],
      ['Order value', '9262.50 PLN', '≤ 30000.00 PLN', 'Pass', 'Order value within the maximum'],
      [
        'Credit',
        '11262.50 PLN',
        '≤ 30000.00 PLN (credit limit)',
        'Pass',
        'Balance + selected option value within limit',
      ],
    ])
    expect(screen.getByRole('region', { name: 'Policy metrics' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run policy' })).not.toBeInTheDocument()
  })

  it('shows Delta as requiring a supervisor with failing and not evaluated rules', () => {
    renderSection(
      { ...DELTA_POLICY, rules: [...DELTA_POLICY.rules.slice(0, 3), CREDIT_NOT_EVALUATED] },
      DELTA_RECOMMENDATION,
    )

    expect(screen.getByText('Requires supervisor approval')).toBeInTheDocument()
    expect(screen.queryByText('No approval needed')).not.toBeInTheDocument()
    expect(rows()).toEqual([
      ['Margin', '14.29%', '≥ 20%', 'Fail', 'Margin below the minimum'],
      ['Discount', '25%', '≤ 15%', 'Fail', 'Requested discount above the maximum'],
      ['Order value', '31500.00 PLN', '≤ 30000.00 PLN', 'Fail', 'Order value above the maximum'],
      ['Credit', '—', '—', 'Not evaluated', 'Credit check skipped'],
    ])
  })

  it('labels example thresholds only when they are examples', () => {
    renderSection({ ...ACME_POLICY, thresholds_are_examples: false })
    expect(screen.queryByText('Example thresholds')).not.toBeInTheDocument()
  })

  it('shows the example thresholds label', () => {
    renderSection(DELTA_POLICY, DELTA_RECOMMENDATION)
    expect(screen.getByText('Example thresholds')).toBeInTheDocument()
  })

  it('offers a re-run for a stale verdict and shows the new result', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = vi.fn(async () => new Promise<Response>((resolve) => (answer = resolve)))
    vi.stubGlobal('fetch', fetchMock)
    renderSection({ ...ACME_POLICY, stale: true })

    expect(screen.getByText(/the result may be out of date/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Re-run policy' }))

    expect(await screen.findByRole('button', { name: 'Running policy…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith(POLICY_PATH, expect.objectContaining({ method: 'POST' }))
    answer(json(200, analysis(ACME_POLICY)))

    await vi.waitFor(() =>
      expect(screen.queryByText(/the result may be out of date/)).not.toBeInTheDocument(),
    )
    expect(screen.getByText('No approval needed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run policy' })).not.toBeInTheDocument()
  })

  it('shows a placeholder with the button when the recommendation has no verdict yet', () => {
    renderSection(null)

    expect(screen.getByText('Policy not evaluated yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run policy' })).toBeEnabled()
  })

  it.each([
    ['missing', null, 'there is no recommendation yet'],
    [
      'failed',
      { ...ACME_RECOMMENDATION, status: 'failed', choice: null } as RecommendationView,
      'the recommendation failed',
    ],
    ['stale', { ...ACME_RECOMMENDATION, stale: true }, 'the recommendation is out of date'],
  ])('explains the missing verdict when the recommendation is %s', (_, recommendation, text) => {
    renderSection(null, recommendation)

    expect(screen.getByText(new RegExp(`^No policy verdict: ${text}`))).toBeInTheDocument()
    expect(screen.queryByText('Policy not evaluated yet')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run policy' })).not.toBeInTheDocument()
  })

  it('keeps a stale verdict visible without a re-run while the recommendation is stale', () => {
    renderSection({ ...ACME_POLICY, stale: true }, { ...ACME_RECOMMENDATION, stale: true })

    expect(screen.getByText(/^No policy verdict: the recommendation is out of date/)).toBeInTheDocument()
    expect(screen.getByText('No approval needed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run policy' })).not.toBeInTheDocument()
  })

  it('shows a failed re-run as an alert with retry', async () => {
    const fetchMock = stubFetch(
      () => json(409, { detail: 'Nothing to evaluate' }),
      () => json(200, analysis(ACME_POLICY)),
    )
    renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run policy' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Re-running the policy failed: Nothing to evaluate')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('No approval needed')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('calls onUnauthorized when the re-run answers 401', async () => {
    stubFetch(() => json(401, { detail: 'Not authenticated' }))
    const onUnauthorized = renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run policy' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
