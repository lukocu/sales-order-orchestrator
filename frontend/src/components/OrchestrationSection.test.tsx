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
  render(<Harness initial={initial} onUnauthorized={onUnauthorized} />)
  return onUnauthorized
}

function stage(title: string): HTMLElement {
  return screen.getByRole('list', { name: title })
}

function task(capability: string): HTMLElement {
  const item = screen
    .getAllByRole('listitem')
    .find((li) => li.querySelector('.check__name')?.textContent?.startsWith(`${capability} →`))
  if (item === undefined) throw new Error(`No task ${capability}`)
  return item
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
  it('shows the ACME plan in two stages with every agent result and the run metrics', () => {
    renderSection(ACME_ORCHESTRATION)

    expect(screen.getByText('Orchestration: Completed')).toBeInTheDocument()
    expect(screen.getByText('Substitute consent: confirmed')).toBeInTheDocument()
    expect(screen.getByText(/^Planner: Shortage of 30 pcs of ABC-100/)).toBeInTheDocument()
    expect(within(stage('Stage 1 — in parallel')).getAllByRole('listitem')).toHaveLength(3)
    expect(
      within(stage('Stage 2 — after: substitute-compatibility')).getAllByRole('listitem'),
    ).toHaveLength(1)

    const compatibility = task('substitute-compatibility')
    expect(compatibility).toHaveTextContent('substitute-compatibility → catalog-agent')
    expect(compatibility).toHaveTextContent('Completed')
    expect(compatibility).toHaveTextContent('look for compatible substitutes')
    expect(compatibility).toHaveTextContent('Attempts1')
    expect(compatibility).toHaveTextContent('Duration1.5 ms')
    expect(compatibility).toHaveTextContent(
      'ABC-110 Czujnik ciśnienia ABC-110 — full compatibility',
    )
    expect(task('substitute-availability')).toHaveTextContent(
      'ABC-110: 40 in stock, covers the shortage',
    )
    expect(task('supplier-availability')).toHaveTextContent(
      'Sensor Parts: 200 pcs on 2026-11-09 (7 days), misses the deadline, covers the shortage',
    )
    expect(task('customer-history')).toHaveTextContent(
      '3 orders, substitutes accepted 2 of 2 offered — accepted substitutes before',
    )

    expect(screen.getByRole('region', { name: 'Orchestration metrics' })).toBeInTheDocument()
    expect(screen.getByText('Wall time 12 ms · sum of steps 8.8 ms')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Re-run orchestrator' })).not.toBeInTheDocument()
    expect(screen.queryByText(/consent to a substitute not confirmed/)).not.toBeInTheDocument()
  })

  it('shows the Omega plan without substitute tasks', () => {
    renderSection(OMEGA_ORCHESTRATION)

    expect(screen.getByText('Substitute consent: refused')).toBeInTheDocument()
    expect(within(stage('Stage 1 — in parallel')).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByText(/^Stage 2/)).not.toBeInTheDocument()
    expect(screen.queryByText(/substitute-compatibility →/)).not.toBeInTheDocument()
    expect(task('supplier-availability')).toHaveTextContent(
      'Valve Works: 80 pcs on 2026-11-10 (5 days), meets the deadline, covers the shortage',
    )
    expect(task('customer-history')).toHaveTextContent('declined substitutes before')
  })

  it('flags the unconfirmed consent of Delta and the shortage nothing covers', () => {
    renderSection(DELTA_ORCHESTRATION)

    expect(screen.getByText('Substitute consent: not confirmed')).toBeInTheDocument()
    expect(screen.getByText('Customer consent to a substitute not confirmed')).toBeInTheDocument()
    expect(task('substitute-availability')).toHaveTextContent(
      'ABC-110: 40 in stock, does not cover the shortage',
    )
    expect(task('supplier-availability')).toHaveTextContent(
      'no deadline, does not cover the shortage',
    )
    expect(task('customer-history')).toHaveTextContent('no substitute history')
  })

  it('shows a partial result with the failed task, its retry and the skipped dependant', () => {
    renderSection(PARTIAL)

    expect(screen.getByText('Orchestration: Partial — some checks failed')).toBeInTheDocument()
    const compatibility = task('substitute-compatibility')
    expect(compatibility).toHaveTextContent('Failed')
    expect(compatibility).toHaveTextContent('Attempts2')
    expect(compatibility).toHaveTextContent('Duration2.8 ms')
    expect(compatibility).toHaveTextContent('ErrorOperationalError')
    const availability = task('substitute-availability')
    expect(availability).toHaveTextContent('Skipped')
    expect(availability).toHaveTextContent('Attempts0')
    expect(availability).toHaveTextContent('Duration—')
    expect(task('supplier-availability')).toHaveTextContent('Completed')
    expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeEnabled()
  })

  it.each([
    [
      { kind: 'planner_failed', code: 'rate_limited', message: 'Planner rate limit reached' },
      'Planner failed: rate_limited',
    ],
    [
      {
        kind: 'plan_rejected',
        code: 'substitute_refused',
        message: 'The plan checks substitutes the customer refused',
      },
      'Plan rejected: substitute_refused',
    ],
    [
      { kind: 'capability_mismatch', code: 'no_agent', message: 'No agent for customer-history' },
      'Capability mismatch: no_agent',
    ],
  ] as [OrchestrationError, string][])('shows a failed orchestration (%o)', (error, heading) => {
    renderSection(failed(error))

    expect(screen.getByText('Orchestration: Failed')).toBeInTheDocument()
    expect(screen.getByText(heading)).toBeInTheDocument()
    expect(screen.getByText(error.message)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run orchestrator' })).toBeInTheDocument()
    const rejected = screen.queryByRole('list', { name: 'Rejected planner choice' })
    if (error.kind === 'plan_rejected') {
      expect(within(rejected!).getAllByRole('listitem')).toHaveLength(4)
      expect(rejected).toHaveTextContent('substitute-compatibility — ABC-100 is short by 30 pcs')
    } else {
      expect(rejected).not.toBeInTheDocument()
    }
  })

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

    expect(await screen.findByText('Orchestration: Completed')).toBeInTheDocument()
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

    expect(await screen.findByText('Orchestration: Completed')).toBeInTheDocument()
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
