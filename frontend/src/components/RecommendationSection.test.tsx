import { fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  rerunRecommendation,
  type Analysis,
  type OrchestrationView,
  type ParsedFields,
  type RecommendationView,
} from '../api/analysis'
import { ACME_ORCHESTRATION, DELTA_ORCHESTRATION } from '../test/orchestrationFixtures'
import {
  ACME_RECOMMENDATION,
  DELTA_RECOMMENDATION,
} from '../test/recommendationFixtures'
import RecommendationSection from './RecommendationSection'

const RECOMMENDATION_PATH = '/api/inquiries/7/recommendation'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(...responses: (() => Response)[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key !== `POST ${RECOMMENDATION_PATH}`) throw new Error(`Unexpected request: ${key}`)
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

function analysis(recommendation: RecommendationView | null): Analysis {
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
    recommendation,
  }
}

// Holds the recommendation and the re-run state like AnalysisPanel does.
function Harness({
  initial,
  orchestration,
  onUnauthorized,
  expectedDeadline,
}: {
  expectedDeadline: string | null
  initial: RecommendationView | null
  orchestration: OrchestrationView | null
  onUnauthorized: () => void
}) {
  const [current, setCurrent] = useState(initial)
  const [running, setRunning] = useState(false)

  async function rerun() {
    setRunning(true)
    try {
      setCurrent((await rerunRecommendation(7)).recommendation ?? null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <RecommendationSection
      inquiryId={7}
      recommendation={current}
      orchestration={orchestration}
      disabled={running}
      running={running}
      onRerun={rerun}
      onUnauthorized={onUnauthorized}
      expectedDeadline={expectedDeadline}
    />
  )
}

function renderSection(
  initial: RecommendationView | null,
  orchestration: OrchestrationView | null = ACME_ORCHESTRATION,
  onUnauthorized = vi.fn(),
  expectedDeadline: string | null = '2026-11-06',
) {
  render(
    <Harness
      initial={initial}
      orchestration={orchestration}
      onUnauthorized={onUnauthorized}
      expectedDeadline={expectedDeadline}
    />,
  )
  return onUnauthorized
}

function table(): HTMLElement {
  return screen.getByRole('table', { name: 'Variant comparison' })
}

function columnNames(): string[] {
  return within(table())
    .getAllByRole('columnheader')
    .slice(1)
    .map((header) => header.textContent ?? '')
}

function items(container: HTMLElement, list: string): string[] {
  return within(within(container).getByRole('list', { name: list }))
    .getAllByRole('listitem')
    .map((item) => item.textContent ?? '')
}

// The recommender, the run metrics and the raw option ids stay in the run inspector.
function expectNoTechnicalText() {
  expect(screen.queryByText(/recommender/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/rule-based/)).not.toBeInTheDocument()
  expect(screen.queryByText(/^stock(\+.*)?$/)).not.toBeInTheDocument()
  expect(screen.queryByText('Option')).not.toBeInTheDocument()
  expect(screen.queryByText(/ in \/ \d+ out|deterministic/)).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: /metrics/i })).not.toBeInTheDocument()
}

describe('RecommendationSection', () => {
  it('shows the ACME substitute first in the comparison table with the justification once', () => {
    renderSection(ACME_RECOMMENDATION, ACME_ORCHESTRATION)

    expect(screen.getByText('Recommendation: Completed')).toBeInTheDocument()
    expect(columnNames()).toEqual([
      'Stock + substitute ABC-110Recommended',
      'Stock only (partial delivery)',
      'Stock + supplier Sensortech Polska',
    ])
    expect(screen.getAllByText('Recommended')).toHaveLength(1)
    expect(screen.getAllByText('Why this recommendation?')).toHaveLength(1)
    expect(screen.getAllByText(/Wybrano opcję stock\+ABC-110/)).toHaveLength(1)

    const cells = (row: string) =>
      within(screen.getByRole('row', { name: new RegExp(`^${row}`) }))
        .getAllByRole('cell')
        .map((cell) => cell.textContent)
    expect(cells('Coverage')).toEqual(['80 / 80 pcs', '50 / 80 pcs', '80 / 80 pcs'])
    expect(cells('Value')).toEqual(['9262.50 PLN', '5700.00 PLN', '9120.00 PLN'])
    expect(cells('Margin')).toEqual(['25.51%', '26.32%', '22.37%'])
    expect(cells('Confidence')).toEqual(['High confidence', 'Low confidence', 'Low confidence'])
    expect(cells('Deadline')).toEqual([
      '2026-11-02, 4 days before the deadline',
      '2026-11-02, 4 days before the deadline',
      '2026-11-09, 3 days after the deadline',
    ])
    expect(cells('Risks')).toEqual([
      'none',
      'Covers 50 of 80 pcs',
      'Delivery on 9 Nov 2026 is after the deadline of 6 Nov 2026',
    ])

    expectNoTechnicalText()
    expect(
      screen.queryByRole('button', { name: 'Re-run recommendation' }),
    ).not.toBeInTheDocument()
  })

  it('shows the Delta combination with no deadline and cited signals in its open details', () => {
    renderSection(DELTA_RECOMMENDATION, DELTA_ORCHESTRATION, vi.fn(), null)

    expect(columnNames()[0]).toContain('Recommended')
    const deadline = screen.getByRole('row', { name: /^Deadline/ })
    expect(
      within(deadline)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(['2026-11-10, no deadline', '2026-11-03, no deadline'])
    const details = document.querySelector('details[open]') as HTMLElement
    expect(items(details, 'Positive')).toEqual(['✓ Substitute ABC-110 is fully compatible · cited'])
    expect(items(details, 'Risks')).toEqual([
      '⚠ Covers 290 of 500 pcs · cited',
      '⚠ Consent to a substitute has not been confirmed · cited',
      '⚠ The shortage is supplied from two sources: a substitute and a supplier · cited',
    ])
    expect(items(details, 'Information')).toEqual([
      'ℹ No deadline in the inquiry',
      'ℹ The customer has not received substitutes before',
    ])
  })

  it('shows a rejected choice as failed with all variants in build order and none recommended', () => {
    renderSection({
      ...ACME_RECOMMENDATION,
      status: 'failed',
      choice: null, // a rejected choice is not stored
      error: {
        kind: 'choice_rejected',
        code: 'foreign_signal',
        message: 'A cited signal does not belong to the chosen option',
      },
    })

    expect(screen.getByText('Recommendation: Failed — no option chosen')).toBeInTheDocument()
    expect(screen.getByText('No option could be recommended this time.')).toBeInTheDocument()
    expect(screen.queryByText(/foreign_signal|Choice rejected/)).not.toBeInTheDocument()
    expect(
      screen.queryByText('A cited signal does not belong to the chosen option'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument()
    expect(screen.queryByText('Why this recommendation?')).not.toBeInTheDocument()
    expect(columnNames()).toEqual([
      'Stock only (partial delivery)',
      'Stock + substitute ABC-110',
      'Stock + supplier Sensortech Polska',
    ])
    expectNoTechnicalText()
    expect(screen.queryByText(/· cited/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run recommendation' })).toBeEnabled()
  })

  it('shows no table when there are no options', () => {
    renderSection({ ...ACME_RECOMMENDATION, options: [], choice: null, status: 'failed' })

    expect(
      screen.getByText('No option could be built from the orchestration results.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows a recommender failure as one sentence, without its code', () => {
    renderSection({
      ...ACME_RECOMMENDATION,
      status: 'failed',
      choice: null,
      error: { kind: 'recommender_failed', code: 'rate_limited', message: 'Rate limit reached' },
    })

    expect(screen.getByText('No option could be recommended this time.')).toBeInTheDocument()
    expect(screen.queryByText(/rate_limited|Rate limit reached/)).not.toBeInTheDocument()
    expect(table()).toBeInTheDocument()
    expectNoTechnicalText()
    expect(screen.getByRole('button', { name: 'Re-run recommendation' })).toBeInTheDocument()
  })

  it('offers a re-run for a stale result', () => {
    renderSection({ ...ACME_RECOMMENDATION, stale: true })

    expect(screen.getByText(/the result may be out of date/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run recommendation' })).toBeInTheDocument()
  })

  it('shows a placeholder with the button when the orchestration has no recommendation yet', () => {
    renderSection(null)

    expect(screen.getByText('Recommendation not run yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run recommendation' })).toBeEnabled()
  })

  it.each([
    ['not orchestrated', null, 'the exception is not orchestrated yet'],
    [
      'failed',
      { ...ACME_ORCHESTRATION, status: 'failed', tasks: [] } as OrchestrationView,
      'the orchestration failed',
    ],
    ['stale', { ...ACME_ORCHESTRATION, stale: true }, 'the orchestration is out of date'],
  ])('explains the missing recommendation when the orchestration is %s', (_, orchestration, text) => {
    renderSection(null, orchestration)

    expect(screen.getByText(new RegExp(`^No recommendation: ${text}`))).toBeInTheDocument()
    expect(screen.queryByText('Recommendation not run yet')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Re-run recommendation' }),
    ).not.toBeInTheDocument()
  })

  it('re-runs a failed recommendation and shows the new result', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = vi.fn(async () => new Promise<Response>((resolve) => (answer = resolve)))
    vi.stubGlobal('fetch', fetchMock)
    renderSection({
      ...ACME_RECOMMENDATION,
      status: 'failed',
      choice: null,
      error: { kind: 'recommender_failed', code: 'timeout', message: 'Timed out' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Re-run recommendation' }))

    expect(await screen.findByRole('button', { name: 'Running recommendation…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith(
      RECOMMENDATION_PATH,
      expect.objectContaining({ method: 'POST' }),
    )
    answer(json(200, analysis(ACME_RECOMMENDATION)))

    expect(await screen.findByText('Recommendation: Completed')).toBeInTheDocument()
    expect(columnNames()[0]).toContain('Recommended')
    expect(
      screen.queryByRole('button', { name: 'Re-run recommendation' }),
    ).not.toBeInTheDocument()
  })

  it('shows a failed re-run as an alert with retry', async () => {
    const fetchMock = stubFetch(
      () => json(409, { detail: 'Nothing to recommend' }),
      () => json(200, analysis(ACME_RECOMMENDATION)),
    )
    renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run recommendation' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Current results from an earlier step are missing.')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Recommendation: Completed')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('calls onUnauthorized when the re-run answers 401', async () => {
    stubFetch(() => json(401, { detail: 'Not authenticated' }))
    const onUnauthorized = renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run recommendation' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
