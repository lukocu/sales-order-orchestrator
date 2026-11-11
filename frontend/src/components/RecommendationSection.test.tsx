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
  ACME_SUPPLIER_OPTION,
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
}: {
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
    />
  )
}

function renderSection(
  initial: RecommendationView | null,
  orchestration: OrchestrationView | null = ACME_ORCHESTRATION,
  onUnauthorized = vi.fn(),
) {
  render(<Harness initial={initial} orchestration={orchestration} onUnauthorized={onUnauthorized} />)
  return onUnauthorized
}

function recommended(): HTMLElement {
  return screen.getByRole('region', { name: 'Recommended option' })
}

function items(container: HTMLElement, list: string): string[] {
  return within(within(container).getByRole('list', { name: list }))
    .getAllByRole('listitem')
    .map((item) => item.textContent ?? '')
}

function option(list: string, id: string): HTMLElement {
  const item = within(screen.getByRole('list', { name: list }))
    .getAllByRole('listitem')
    .find((li) => li.querySelector('dd')?.textContent === id)
  if (item === undefined) throw new Error(`No option ${id}`)
  return item
}

describe('RecommendationSection', () => {
  it('shows the ACME substitute as a HIGH recommendation with its cited positives', () => {
    renderSection(ACME_RECOMMENDATION)

    expect(screen.getByText('Recommendation: Completed')).toBeInTheDocument()
    expect(screen.getByText(/recommender rule-based/)).toBeInTheDocument()
    const card = recommended()
    expect(card).toHaveTextContent('Stock + substitute')
    expect(card).toHaveTextContent('HIGH confidence')
    expect(card).toHaveTextContent('Optionstock+ABC-110')
    expect(card).toHaveTextContent(
      '50 × ABC-100 Czujnik ciśnienia ABC-100 — own stock, available 2026-11-02, 114.00 PLN/pc',
    )
    expect(card).toHaveTextContent(
      '30 × ABC-110 Czujnik ciśnienia ABC-110 — substitute from stock, available 2026-11-02, ' +
        '118.75 PLN/pc',
    )
    expect(card).toHaveTextContent('Coverage80 / 80 pcs')
    expect(card).toHaveTextContent('Fulfilled2026-11-02, meets the deadline')
    expect(card).toHaveTextContent('Value9262.50 PLN')
    expect(card).toHaveTextContent('Cost6900.00 PLN')
    expect(card).toHaveTextContent('Margin25.51%')
    expect(within(card).getByText('Why this recommendation?')).toBeInTheDocument()
    expect(card).toHaveTextContent('Wybrano opcję stock+ABC-110: pokrycie 80/80 szt.')
    const positives = items(card, 'Positive')
    expect(positives).toHaveLength(5)
    expect(positives.every((item) => item.endsWith(' · cited'))).toBe(true)
    expect(positives[2]).toContain('Zamiennik ABC-110 w pełni zgodny')
    expect(within(card).queryByRole('list', { name: 'Risks' })).not.toBeInTheDocument()

    const others = screen.getByRole('list', { name: 'Other options' })
    expect(others.querySelectorAll(':scope > li')).toHaveLength(2)
    const supplier = option('Other options', 'stock+supplier:Sensortech Polska')
    expect(supplier).toHaveTextContent('Stock + supplier')
    expect(supplier).toHaveTextContent('LOW confidence')
    expect(supplier).toHaveTextContent('supplier Sensortech Polska, available 2026-11-09')
    expect(supplier).toHaveTextContent('Fulfilled2026-11-09, misses the deadline')
    expect(items(supplier, 'Risks')).toEqual(['⚠ Realizacja 2026-11-09 po terminie 2026-11-06'])
    expect(option('Other options', 'stock')).toHaveTextContent('Partial delivery from stock')

    expect(screen.getByRole('region', { name: 'Recommendation metrics' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Re-run recommendation' }),
    ).not.toBeInTheDocument()
  })

  it('shows the Delta combination as LOW with cited risks and uncited information', () => {
    renderSection(DELTA_RECOMMENDATION, DELTA_ORCHESTRATION)

    const card = recommended()
    expect(card).toHaveTextContent('Stock + substitute + supplier')
    expect(card).toHaveTextContent('LOW confidence')
    expect(card).toHaveTextContent('Coverage290 / 500 pcs')
    expect(card).toHaveTextContent('Fulfilled2026-11-10, no deadline')
    expect(card).toHaveTextContent('Margin14.29%')
    expect(items(card, 'Positive')).toEqual(['✓ Zamiennik ABC-110 w pełni zgodny · cited'])
    expect(items(card, 'Risks')).toEqual([
      '⚠ Pokrywa 290 z 500 szt. · cited',
      '⚠ Brak potwierdzenia zgody na zamiennik · cited',
      '⚠ Brak uzupełniany z dwóch źródeł: zamiennik i dostawca · cited',
    ])
    expect(items(card, 'Information')).toEqual([
      'ℹ Zapytanie bez terminu',
      'ℹ Klient nie dostawał dotąd zamienników',
    ])
  })

  it('keeps a check skipped for an alternative visible as information', () => {
    const supplier = {
      ...ACME_SUPPLIER_OPTION,
      signals: [
        ...ACME_SUPPLIER_OPTION.signals,
        {
          code: 'alternative_not_checked:customer-history',
          polarity: 'info' as const,
          label: 'Alternatywy nie sprawdzono: historia klienta',
        },
      ],
    }
    renderSection({
      ...ACME_RECOMMENDATION,
      options: [ACME_RECOMMENDATION.options[0], ACME_RECOMMENDATION.options[1], supplier],
    })

    expect(items(option('Other options', supplier.id), 'Information')).toEqual([
      'ℹ Alternatywy nie sprawdzono: historia klienta',
    ])
  })

  it('shows a rejected choice as failed with all options, the error code and a re-run', () => {
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
    expect(screen.getByText('Choice rejected: foreign_signal')).toBeInTheDocument()
    expect(
      screen.getByText('A cited signal does not belong to the chosen option'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Recommended option' })).not.toBeInTheDocument()
    expect(option('Options', 'stock+ABC-110')).toHaveTextContent('HIGH confidence')
    expect(option('Options', 'stock')).toHaveTextContent('LOW confidence')
    expect(screen.queryByText(/· cited/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run recommendation' })).toBeEnabled()
  })

  it('shows a recommender failure with its code', () => {
    renderSection({
      ...ACME_RECOMMENDATION,
      status: 'failed',
      choice: null,
      error: { kind: 'recommender_failed', code: 'rate_limited', message: 'Rate limit reached' },
    })

    expect(screen.getByText('Recommender failed: rate_limited')).toBeInTheDocument()
    expect(option('Options', 'stock')).toHaveTextContent('Partial delivery from stock')
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
    expect(recommended()).toHaveTextContent('HIGH confidence')
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
    expect(alert).toHaveTextContent('Nothing to recommend')
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
