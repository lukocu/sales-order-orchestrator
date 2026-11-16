import { createMemoryHistory, RouterContextProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  rerunOrchestration,
  type Analysis,
  type OrchestrationError,
  type OrchestrationView,
  type ParsedFields,
} from '../api/analysis'
import {
  ACME_ORCHESTRATION,
  AVAILABILITY_TASK,
  COMPATIBILITY_TASK,
  DELTA_ORCHESTRATION,
  OMEGA_ORCHESTRATION,
  orchestrationRun,
} from '../test/orchestrationFixtures'
import { createAppRouter } from '../router'
import OrchestrationSection from './OrchestrationSection'

const ORCHESTRATION_PATH = '/api/inquiries/7/orchestration'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(...responses: (() => Response)[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    if (key !== `POST ${ORCHESTRATION_PATH}`) throw new Error(`Unexpected request: ${key}`)
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

function analysis(orchestration: OrchestrationView | null): Analysis {
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
    orchestration,
  }
}

// Holds the orchestration and the re-run state like AnalysisPanel does.
function Harness({
  initial,
  onUnauthorized,
}: {
  initial: OrchestrationView | null
  onUnauthorized: () => void
}) {
  const [current, setCurrent] = useState(initial)
  const [running, setRunning] = useState(false)

  async function rerun() {
    setRunning(true)
    try {
      setCurrent((await rerunOrchestration(7)).orchestration)
    } finally {
      setRunning(false)
    }
  }

  return (
    <OrchestrationSection
      inquiryId={7}
      orchestration={current}
      disabled={running}
      running={running}
      onRerun={rerun}
      onUnauthorized={onUnauthorized}
    />
  )
}

function renderSection(initial: OrchestrationView | null, onUnauthorized = vi.fn()) {
  // A failed orchestration links to the run inspector, so the section needs a router (not
  // loaded: the link only has to render).
  const router = createAppRouter(createMemoryHistory({ initialEntries: ['/inquiries/7'] }))
  render(
    <RouterContextProvider router={router}>
      <Harness initial={initial} onUnauthorized={onUnauthorized} />
    </RouterContextProvider>,
  )
  return onUnauthorized
}

function findings(): HTMLElement {
  return screen.getByRole('list', { name: 'Findings of the additional checks' })
}

// A finding by the readable name of its check.
function task(label: string): HTMLElement {
  const item = within(findings())
    .getAllByRole('listitem')
    .find((li) => li.querySelector('.check__name')?.textContent === label)
  if (item === undefined) throw new Error(`No task ${label}`)
  return item
}

// Nothing of how the checks were planned, run or priced reaches the business layer.
function expectNoTechnicalText() {
  for (const text of [
    /planner/i,
    /Stage \d/,
    /→/,
    /-agent\b/,
    /Attempts/,
    /Wall time/,
    / in \/ \d+ out/,
    /deterministic/,
    /look for compatible substitutes/,
  ]) {
    expect(screen.queryByText(text)).not.toBeInTheDocument()
  }
  expect(screen.queryByRole('region', { name: /metrics/i })).not.toBeInTheDocument()
}

const PARTIAL: OrchestrationView = {
  ...ACME_ORCHESTRATION,
  status: 'partial',
  tasks: ACME_ORCHESTRATION.tasks.map((item) => {
    if (item.capability === COMPATIBILITY_TASK.capability) {
      return {
        ...item,
        status: 'failed',
        steps: ['agent:substitute-compatibility', 'agent:substitute-compatibility#2'],
        error_type: 'OperationalError',
        result: null,
      }
    }
    if (item.capability === AVAILABILITY_TASK.capability) {
      return { ...item, status: 'skipped', steps: [], result: null }
    }
    return item
  }),
  run: orchestrationRun([
    ['agent:substitute-compatibility', 1.5],
    ['agent:supplier-availability', 2.5],
    ['agent:customer-history', 3],
    ['agent:substitute-compatibility#2', 1.25],
  ]),
}

function failed(error: OrchestrationError): OrchestrationView {
  return { ...ACME_ORCHESTRATION, status: 'failed', tasks: [], error }
}

describe('OrchestrationSection', () => {
  it('shows the ACME findings under readable check names, without the plan or metrics', () => {
    renderSection(ACME_ORCHESTRATION)

    expect(screen.getByText('Additional checks: completed')).toBeInTheDocument()
    expect(screen.getByText('Substitute consent: confirmed')).toBeInTheDocument()
    expect(within(findings()).getAllByRole('listitem')).toHaveLength(4)

    const compatibility = task('Compatible substitutes')
    expect(compatibility).toHaveTextContent('Completed')
    expect(compatibility).toHaveTextContent(
      'ABC-110 Czujnik ciśnienia ABC-110 — full compatibility',
    )
    expect(task('Substitute stock')).toHaveTextContent('ABC-110: 40 in stock, covers the shortage')
    expect(task('Supplier deliveries')).toHaveTextContent(
      'Sensor Parts: 200 pcs on 2026-11-09 (7 days), misses the deadline, covers the shortage',
    )
    expect(task('Customer history')).toHaveTextContent(
      '3 orders, substitutes accepted 2 of 2 offered — accepted substitutes before',
    )

    expectNoTechnicalText()
    expect(screen.queryByText(/Shortage of 30 pcs of ABC-100/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run orchestrator' })).not.toBeInTheDocument()
    expect(screen.queryByText(/consent to a substitute not confirmed/)).not.toBeInTheDocument()
  })

  it('shows the Omega findings without substitute checks', () => {
    renderSection(OMEGA_ORCHESTRATION)

    expect(screen.getByText('Substitute consent: refused')).toBeInTheDocument()
    expect(within(findings()).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByText('Compatible substitutes')).not.toBeInTheDocument()
    expect(task('Supplier deliveries')).toHaveTextContent(
      'Valve Works: 80 pcs on 2026-11-10 (5 days), meets the deadline, covers the shortage',
    )
    expect(task('Customer history')).toHaveTextContent('declined substitutes before')
    expectNoTechnicalText()
  })

  it('flags the unconfirmed consent of Delta and the shortage nothing covers', () => {
    renderSection(DELTA_ORCHESTRATION)

    expect(screen.getByText('Substitute consent: not confirmed')).toBeInTheDocument()
    expect(screen.getByText('Customer consent to a substitute not confirmed')).toBeInTheDocument()
    expect(task('Substitute stock')).toHaveTextContent(
      'ABC-110: 40 in stock, does not cover the shortage',
    )
    expect(task('Supplier deliveries')).toHaveTextContent(
      'no deadline, does not cover the shortage',
    )
    expect(task('Customer history')).toHaveTextContent('no substitute history')
  })

  it('says a failed or skipped check is unavailable, without its error type', () => {
    renderSection(PARTIAL)

    expect(screen.getByText('Additional checks: some are unavailable')).toBeInTheDocument()
    const compatibility = task('Compatible substitutes')
    expect(compatibility).toHaveTextContent('Unavailable')
    expect(compatibility).toHaveTextContent('This check is unavailable.')
    const availability = task('Substitute stock')
    expect(availability).toHaveTextContent('Unavailable')
    expect(availability).toHaveTextContent(
      'This check is unavailable because an earlier check did not complete.',
    )
    expect(task('Supplier deliveries')).toHaveTextContent('Completed')
    expect(screen.queryByText(/OperationalError/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^(Failed|Skipped)$/)).not.toBeInTheDocument()
    expectNoTechnicalText()
    expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeEnabled()
  })

  it.each([
    { kind: 'planner_failed', code: 'rate_limited', message: 'Planner rate limit reached' },
    {
      kind: 'plan_rejected',
      code: 'substitute_refused',
      message: 'The plan checks substitutes the customer refused',
    },
    { kind: 'capability_mismatch', code: 'no_agent', message: 'No agent for customer-history' },
  ] as OrchestrationError[])(
    'shows a failed orchestration as one sentence with the inspector link (%o)',
    (error) => {
      renderSection(failed(error))

      expect(screen.getByText('Additional checks: failed')).toBeInTheDocument()
      expect(
        screen.getByText(
          'The additional checks could not be prepared, so their results are unavailable.',
        ),
      ).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Technical details' })).toHaveAttribute(
        'href',
        '/inquiries/7/run',
      )
      expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeInTheDocument()
      expect(screen.queryByText(new RegExp(error.code))).not.toBeInTheDocument()
      expect(screen.queryByText(error.message)).not.toBeInTheDocument()
      expect(
        screen.queryByRole('list', { name: 'Rejected planner choice' }),
      ).not.toBeInTheDocument()
      expectNoTechnicalText()
    },
  )

  it('shows a placeholder with the button when the exception has no orchestration yet', () => {
    renderSection(null)

    expect(screen.getByText('Orchestration not run yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeEnabled()
  })

  it('offers a re-run for a stale result', () => {
    renderSection({ ...ACME_ORCHESTRATION, stale: true })

    expect(screen.getByText(/the result may be out of date/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeInTheDocument()
  })

  it('re-runs a failed orchestration and shows the new result', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = vi.fn(async () => new Promise<Response>((resolve) => (answer = resolve)))
    vi.stubGlobal('fetch', fetchMock)
    renderSection(
      failed({ kind: 'planner_failed', code: 'unavailable', message: 'Planner unavailable' }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Re-run orchestrator' }))

    expect(await screen.findByRole('button', { name: 'Running orchestrator…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith(
      ORCHESTRATION_PATH,
      expect.objectContaining({ method: 'POST' }),
    )
    answer(json(200, analysis(ACME_ORCHESTRATION)))

    expect(await screen.findByText('Additional checks: completed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run orchestrator' })).not.toBeInTheDocument()
  })

  it('shows a failed re-run as an alert with retry', async () => {
    const fetchMock = stubFetch(
      () => json(409, { detail: 'Nothing to orchestrate' }),
      () => json(200, analysis(ACME_ORCHESTRATION)),
    )
    renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run orchestrator' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Nothing to orchestrate')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Additional checks: completed')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('calls onUnauthorized when the re-run answers 401', async () => {
    stubFetch(() => json(401, { detail: 'Not authenticated' }))
    const onUnauthorized = renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Re-run orchestrator' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})
