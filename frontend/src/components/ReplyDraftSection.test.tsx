import { fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  decideAsSupervisor,
  decideDraft,
  editDraft,
  regenerateDraft,
  type Analysis,
  type ParsedFields,
  type RecommendationView,
  type ReplyDraftDecision,
  type ReplyDraftStatus,
  type ReplyDraftView,
} from '../api/analysis'
import type { User } from '../api/auth'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'
import {
  ACME_APPROVED,
  ACME_DRAFT,
  ACME_EDITED,
  ACME_EDITED_DRAFT,
  ACME_REJECTED_EARLIER,
  DELTA_AWAITING,
  DELTA_DRAFT,
  DELTA_SUBMITTED,
  DELTA_SUPERVISOR_REJECTED,
} from '../test/replyDraftFixtures'
import { OTHER_SUPERVISOR, SALES, SUPERVISOR } from '../test/userFixtures'
import ReplyDraftSection, { DecisionHistory } from './ReplyDraftSection'

const DRAFT_PATH = '/api/inquiries/7/draft'
const DECISION_PATH = '/api/inquiries/7/draft/decision'
const SUPERVISOR_DECISION_PATH = '/api/inquiries/7/draft/supervisor-decision'

type Handler = () => Response

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Routes are keyed "METHOD /path"; an array answers with its items in order (the last one
// repeats).
function stubApi(routes: Record<string, Handler[]>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const route = routes[key]
    if (route === undefined) throw new Error(`Unexpected request: ${key}`)
    const handler = route.length > 1 ? route.shift()! : route[0]
    return handler()
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function sentBody(fetchMock: ReturnType<typeof stubApi>, method: string): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === method)
  return JSON.parse(String(call?.[1]?.body))
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

function analysis(draft: ReplyDraftView | null, decisions: ReplyDraftDecision[] = []): Analysis {
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
    policy: ACME_POLICY,
    draft,
    decisions,
  }
}

// Holds the draft and the busy state like AnalysisPanel does.
function Harness({
  initial,
  recommendation,
  user,
  onUnauthorized,
}: {
  initial: ReplyDraftView | null
  recommendation: RecommendationView | null
  user: User
  onUnauthorized: () => void
}) {
  const [current, setCurrent] = useState(initial)
  const [busy, setBusy] = useState<'drafting' | 'deciding' | null>(null)

  async function run(kind: 'drafting' | 'deciding', send: () => Promise<Analysis>) {
    setBusy(kind)
    try {
      setCurrent((await send()).draft ?? null)
    } finally {
      setBusy(null)
    }
  }

  return (
    <ReplyDraftSection
      inquiryId={7}
      user={user}
      draft={current}
      recommendation={recommendation}
      disabled={busy !== null}
      drafting={busy === 'drafting'}
      deciding={busy === 'deciding'}
      onRegenerate={() => run('drafting', () => regenerateDraft(7))}
      onEdit={(updatedAt, edit) => run('deciding', () => editDraft(7, updatedAt, edit))}
      onDecide={(updatedAt, action, reason) =>
        run('deciding', () => decideDraft(7, updatedAt, action, reason))
      }
      onSupervisorDecide={(updatedAt, action, reason) =>
        run('deciding', () => decideAsSupervisor(7, updatedAt, action, reason))
      }
      onUnauthorized={onUnauthorized}
    />
  )
}

function renderSection(
  initial: ReplyDraftView | null,
  recommendation: RecommendationView | null = ACME_RECOMMENDATION,
  onUnauthorized = vi.fn(),
  user: User = SALES,
) {
  render(
    <Harness
      initial={initial}
      recommendation={recommendation}
      user={user}
      onUnauthorized={onUnauthorized}
    />,
  )
  return onUnauthorized
}

function renderAs(user: User, initial: ReplyDraftView | null) {
  return renderSection(initial, ACME_RECOMMENDATION, vi.fn(), user)
}

function decisionButtons(name = 'Decision'): string[] {
  const bar = screen.queryByRole('group', { name })
  if (bar === null) return []
  return within(bar)
    .getAllByRole('button')
    .map((button) => button.textContent ?? '')
}

describe('ReplyDraftSection', () => {
  it('shows the e-mail preview, why this recommendation and the verdict in force', () => {
    renderSection(ACME_DRAFT)

    expect(screen.getByText('Draft')).toBeInTheDocument()
    const preview = screen.getByRole('region', { name: 'E-mail preview' })
    expect(preview).toHaveTextContent('Subject: Re: Zapytanie ofertowe ABC-100')
    expect(preview).toHaveTextContent('Razem: 9 262,50 PLN netto.')
    expect(screen.getByText('Why this recommendation?')).toBeInTheDocument()
    expect(screen.getByText(/^Wybrano opcję stock\+ABC-110/)).toBeInTheDocument()
    expect(
      within(screen.getByRole('list', { name: 'Cited signals' })).getAllByRole('listitem'),
    ).toHaveLength(3)
    expect(screen.getByRole('table', { name: /^Policy verdict in force:/ })).toHaveTextContent(
      'No approval needed',
    )
    expect(screen.getByRole('region', { name: 'Draft metrics' })).toBeInTheDocument()
    expect(screen.queryByText(/fallback text/)).not.toBeInTheDocument()
    expect(decisionButtons()).toEqual(['Approve', 'Edit offer', 'Reject'])
    expect(screen.queryByRole('button', { name: 'Regenerate draft' })).not.toBeInTheDocument()
  })

  it('marks the fallback text and the verdict of an edited offer', () => {
    renderSection({ ...ACME_EDITED_DRAFT, text_source: 'fallback' })

    expect(screen.getByText(/uses the fixed fallback text/)).toBeInTheDocument()
    expect(screen.getByText(/· edited offer$/)).toBeInTheDocument()
    const table = screen.getByRole('table', { name: /^Policy verdict in force \(edited offer\)/ })
    expect(table).toHaveTextContent('Requires supervisor approval')
    expect(table).toHaveTextContent('Offered discount above the maximum')
  })

  it.each<[ReplyDraftStatus, string]>([
    ['ready_to_send', 'Ready to send (sending is simulated)'],
    ['awaiting_supervisor', 'Awaiting supervisor approval'],
    ['rejected', 'Rejected'],
  ])('shows the %s status without decision actions', (status, label) => {
    renderSection({ ...ACME_DRAFT, status })

    expect(screen.getByText(label)).toBeInTheDocument()
    expect(decisionButtons()).toEqual([])
  })

  it('offers Regenerate only for a rejected draft among the decided ones', () => {
    renderSection({ ...ACME_DRAFT, status: 'rejected' })
    expect(screen.getByRole('button', { name: 'Regenerate draft' })).toBeEnabled()
  })

  it.each<ReplyDraftStatus>(['ready_to_send', 'awaiting_supervisor'])(
    'does not offer Regenerate for a %s draft',
    (status) => {
      renderSection({ ...ACME_DRAFT, status })
      expect(screen.queryByRole('button', { name: 'Regenerate draft' })).not.toBeInTheDocument()
    },
  )

  it('hides the actions of a stale draft and offers Regenerate', () => {
    renderSection({ ...ACME_DRAFT, stale: true })

    expect(screen.getByText(/the draft may be out of date/)).toBeInTheDocument()
    expect(decisionButtons()).toEqual([])
    expect(screen.getByRole('button', { name: 'Regenerate draft' })).toBeEnabled()
  })

  it.each(['ready_to_send', 'awaiting_supervisor'] as const)(
    'offers no Regenerate for a stale %s draft',
    (status) => {
      renderSection({ ...ACME_DRAFT, status, stale: true })

      expect(decisionButtons()).toEqual([])
      expect(screen.queryByRole('button', { name: 'Regenerate draft' })).not.toBeInTheDocument()
    },
  )

  it('shows a placeholder with Regenerate when there is no draft yet', () => {
    renderSection(null)

    expect(screen.getByText('Draft not generated yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Regenerate draft' })).toBeEnabled()
  })

  it.each([
    ['missing', null, 'there is no recommendation yet'],
    [
      'failed',
      { ...ACME_RECOMMENDATION, status: 'failed', choice: null } as RecommendationView,
      'the recommendation has no chosen option',
    ],
    ['stale', { ...ACME_RECOMMENDATION, stale: true }, 'the recommendation is out of date'],
  ])('explains the missing draft when the recommendation is %s', (_, recommendation, text) => {
    renderSection(null, recommendation)

    expect(screen.getByText(new RegExp(`^No draft: ${text}`))).toBeInTheDocument()
    expect(screen.queryByText('Draft not generated yet')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Regenerate draft' })).not.toBeInTheDocument()
  })

  it('regenerates the draft and shows the new one', async () => {
    const fetchMock = stubApi({ [`POST ${DRAFT_PATH}`]: [() => json(200, analysis(ACME_DRAFT))] })
    renderSection({ ...ACME_DRAFT, status: 'rejected' })

    fireEvent.click(screen.getByRole('button', { name: 'Regenerate draft' }))

    expect(await screen.findByText('Draft')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Regenerate draft' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(DRAFT_PATH, expect.objectContaining({ method: 'POST' }))
  })

  it('shows a failed regeneration as an alert with retry', async () => {
    const fetchMock = stubApi({
      [`POST ${DRAFT_PATH}`]: [
        () => json(409, { detail: 'Nothing to draft' }),
        () => json(200, analysis(ACME_DRAFT)),
      ],
    })
    renderSection(null)
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate draft' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Regenerating the draft failed: Nothing to draft')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Draft')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('approves with an optional comment', async () => {
    const fetchMock = stubApi({
      [`POST ${DECISION_PATH}`]: [
        () => json(200, analysis({ ...ACME_DRAFT, status: 'ready_to_send' }, [ACME_APPROVED])),
      ],
    })
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByText('Ready to send (sending is simulated)')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST')).toEqual({
      updated_at: ACME_DRAFT.updated_at,
      action: 'approve',
      reason: null,
    })
    expect(screen.queryByRole('form', { name: 'Approve draft' })).not.toBeInTheDocument()
  })

  it('sends the approval comment when one is given', async () => {
    const fetchMock = stubApi({
      [`POST ${DECISION_PATH}`]: [
        () => json(200, analysis({ ...DELTA_DRAFT, status: 'awaiting_supervisor' })),
      ],
    })
    renderSection(DELTA_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    fireEvent.change(screen.getByLabelText('Comment (optional)'), {
      target: { value: '  Ważny klient ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByText('Awaiting supervisor approval')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST')).toMatchObject({
      action: 'approve',
      reason: 'Ważny klient',
    })
  })

  it('requires a reason to reject', async () => {
    const fetchMock = stubApi({
      [`POST ${DECISION_PATH}`]: [() => json(200, analysis({ ...ACME_DRAFT, status: 'rejected' }))],
    })
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a reason for the rejection.')
    expect(fetchMock).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Za drogo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    expect(await screen.findByText('Rejected')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST')).toEqual({
      updated_at: ACME_DRAFT.updated_at,
      action: 'reject',
      reason: 'Za drogo',
    })
  })

  it('cancels a decision form back to the actions', () => {
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(decisionButtons()).toEqual(['Approve', 'Edit offer', 'Reject'])
  })

  it('shows a refused decision at its form', async () => {
    stubApi({ [`POST ${DECISION_PATH}`]: [() => json(409, { detail: 'Policy verdict missing' })] })
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Policy verdict missing')
    expect(screen.getByRole('button', { name: 'Confirm approval' })).toBeEnabled()
  })

  it('edits the unit price with a required reason', async () => {
    const fetchMock = stubApi({
      [`PUT ${DRAFT_PATH}`]: [() => json(200, analysis(ACME_EDITED_DRAFT, [ACME_EDITED]))],
    })
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Edit offer' }))
    expect(screen.getByLabelText('Option')).toHaveValue('stock+ABC-110')
    const price = screen.getByLabelText('Unit price of ABC-100, own stock')
    expect(price).toHaveValue('114.00')
    expect(screen.getByLabelText('Quantity of ABC-110, substitute from stock')).toHaveValue('30')
    fireEvent.change(price, { target: { value: '95,00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a reason for the edit.')
    expect(fetchMock).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Negocjacje cenowe' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }))

    expect(await screen.findByText(/· edited offer$/)).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT')).toEqual({
      updated_at: ACME_DRAFT.updated_at,
      option_id: 'stock+ABC-110',
      lines: [
        { product_code: 'ABC-100', quantity: 50, unit_price: '95.00' },
        { product_code: 'ABC-110', quantity: 30, unit_price: '118.75' },
      ],
      reason: 'Negocjacje cenowe',
    })
    expect(screen.queryByRole('form', { name: 'Edit offer' })).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: /edited offer/ })).toHaveTextContent('Fail')
  })

  it('switches the edit to another option with its lines', () => {
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Edit offer' }))
    fireEvent.change(screen.getByLabelText('Option'), { target: { value: 'stock' } })

    expect(screen.getByLabelText('Quantity of ABC-100, own stock')).toHaveValue('50')
    expect(
      screen.queryByLabelText('Quantity of ABC-110, substitute from stock'),
    ).not.toBeInTheDocument()
  })

  it.each([
    ['a quantity that is not a whole number', 'Quantity of ABC-100, own stock', '2.5', 'Quantity'],
    ['a unit price with three decimals', 'Unit price of ABC-100, own stock', '1.005', 'Unit price'],
  ])('rejects %s before sending', (_, label, value, message) => {
    const fetchMock = stubApi({})
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Edit offer' }))
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Powód' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }))

    expect(screen.getByRole('alert')).toHaveTextContent(new RegExp(`^${message}`))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the API message of an invalid edit', async () => {
    stubApi({
      [`PUT ${DRAFT_PATH}`]: [() => json(422, { detail: 'Quantity must be at least 1' })],
    })
    renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Edit offer' }))
    fireEvent.change(screen.getByLabelText('Quantity of ABC-100, own stock'), {
      target: { value: '0' },
    })
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Powód' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Quantity must be at least 1')
    expect(screen.getByRole('form', { name: 'Edit offer' })).toBeInTheDocument()
  })

  it('calls onUnauthorized when a decision answers 401', async () => {
    stubApi({ [`POST ${DECISION_PATH}`]: [() => json(401, { detail: 'Not authenticated' })] })
    const onUnauthorized = renderSection(ACME_DRAFT)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })

  it('calls onUnauthorized when the regeneration answers 401', async () => {
    stubApi({ [`POST ${DRAFT_PATH}`]: [() => json(401, { detail: 'Not authenticated' })] })
    const onUnauthorized = renderSection(null)

    fireEvent.click(screen.getByRole('button', { name: 'Regenerate draft' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})

describe("ReplyDraftSection: the supervisor's decision", () => {
  const supervisorButtons = () => decisionButtons('Supervisor decision')

  it("offers a supervisor Approve and Reject on another user's submission", () => {
    renderAs(SUPERVISOR, DELTA_AWAITING)

    expect(screen.getByText('Awaiting supervisor approval')).toBeInTheDocument()
    expect(supervisorButtons()).toEqual(['Approve', 'Reject'])
    expect(decisionButtons()).toEqual([])
    expect(screen.queryByText(/You submitted this draft/)).not.toBeInTheDocument()
    expect(screen.queryByText('Waiting for a supervisor decision.')).not.toBeInTheDocument()
    // The verdict in force stays in view for the decision.
    expect(screen.getByRole('table', { name: /^Policy verdict in force:/ })).toHaveTextContent(
      'Requires supervisor approval',
    )
  })

  it('offers a supervisor only Reject on their own submission, with an explanation', () => {
    renderAs(SUPERVISOR, { ...DELTA_AWAITING, submitted_by: SUPERVISOR.id })

    expect(
      screen.getByText(
        'You submitted this draft; another supervisor must approve it. You can reject it to ' +
          'start over.',
      ),
    ).toBeInTheDocument()
    expect(supervisorButtons()).toEqual(['Reject'])
  })

  it("offers another supervisor both actions on a supervisor's submission", () => {
    renderAs(OTHER_SUPERVISOR, { ...DELTA_AWAITING, submitted_by: SUPERVISOR.id })

    expect(supervisorButtons()).toEqual(['Approve', 'Reject'])
  })

  it('offers a supervisor both actions when the submitter is unknown', () => {
    renderAs(SUPERVISOR, { ...DELTA_AWAITING, submitted_by: null })

    expect(supervisorButtons()).toEqual(['Approve', 'Reject'])
  })

  it('shows the salesperson a waiting note without supervisor actions', () => {
    renderAs(SALES, DELTA_AWAITING)

    expect(screen.getByText('Waiting for a supervisor decision.')).toBeInTheDocument()
    expect(supervisorButtons()).toEqual([])
    expect(decisionButtons()).toEqual([])
  })

  it('offers no supervisor actions on a stale draft awaiting the supervisor', () => {
    renderAs(SUPERVISOR, { ...DELTA_AWAITING, stale: true })

    expect(supervisorButtons()).toEqual([])
    expect(screen.queryByText('Waiting for a supervisor decision.')).not.toBeInTheDocument()
  })

  it.each<ReplyDraftStatus>(['draft', 'ready_to_send', 'rejected'])(
    'offers no supervisor actions on a %s draft',
    (status) => {
      renderAs(SUPERVISOR, { ...DELTA_AWAITING, status, submitted_by: null })

      expect(supervisorButtons()).toEqual([])
    },
  )

  it('keeps the salesperson actions for a supervisor on a draft', () => {
    renderAs(SUPERVISOR, ACME_DRAFT)

    expect(decisionButtons()).toEqual(['Approve', 'Edit offer', 'Reject'])
    expect(supervisorButtons()).toEqual([])
  })

  it.each([
    ['approve', 'Approve', 'Confirm approval', 'Enter a reason for the approval.', 'ready_to_send'],
    ['reject', 'Reject', 'Confirm rejection', 'Enter a reason for the rejection.', 'rejected'],
  ] as const)('requires a reason to %s as the supervisor', async (action, open, confirm, message, after) => {
    const fetchMock = stubApi({
      [`POST ${SUPERVISOR_DECISION_PATH}`]: [
        () => json(200, analysis({ ...DELTA_AWAITING, status: after, submitted_by: null })),
      ],
    })
    renderAs(SUPERVISOR, DELTA_AWAITING)

    const group = screen.getByRole('group', { name: 'Supervisor decision' })
    fireEvent.click(within(group).getByRole('button', { name: open }))
    expect(screen.getByRole('form', { name: `${open} as supervisor` })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: confirm }))

    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(fetchMock).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: ' Decyzja przełożonego ' },
    })
    fireEvent.click(screen.getByRole('button', { name: confirm }))

    await vi.waitFor(() =>
      expect(screen.queryByRole('form', { name: `${open} as supervisor` })).not.toBeInTheDocument(),
    )
    expect(sentBody(fetchMock, 'POST')).toEqual({
      updated_at: DELTA_AWAITING.updated_at,
      action,
      reason: 'Decyzja przełożonego',
    })
    expect(supervisorButtons()).toEqual([])
  })

  it("shows a refused supervisor's decision at its form", async () => {
    stubApi({
      [`POST ${SUPERVISOR_DECISION_PATH}`]: [
        () => json(409, { detail: 'Cannot approve your own submission' }),
      ],
    })
    renderAs(SUPERVISOR, DELTA_AWAITING)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'OK' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Cannot approve your own submission',
    )
    expect(screen.getByRole('form', { name: 'Approve as supervisor' })).toBeInTheDocument()
  })

  it("calls onUnauthorized when the supervisor's decision answers 401", async () => {
    stubApi({
      [`POST ${SUPERVISOR_DECISION_PATH}`]: [() => json(401, { detail: 'Not authenticated' })],
    })
    const onUnauthorized = renderSection(DELTA_AWAITING, ACME_RECOMMENDATION, vi.fn(), SUPERVISOR)

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Nie' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }))

    await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
  })
})

describe('DecisionHistory', () => {
  it('lists each decision with who, when, why and an earlier version mark', () => {
    render(
      <DecisionHistory
        inquiryId={7}
        decisions={[ACME_REJECTED_EARLIER, ACME_EDITED, ACME_APPROVED]}
      />,
    )

    const items = within(
      screen.getByRole('region', { name: 'Decision history' }),
    ).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Rejectedearlier version')
    expect(items[0]).toHaveTextContent('Anna Kowalska')
    expect(items[0]).toHaveTextContent('Klient zmienił ilość')
    expect(items[1]).toHaveTextContent('Negocjacje cenowe')
    expect(items[1]).toHaveTextContent('Requires supervisor approval (failing: Margin, Discount)')
    expect(items[1]).not.toHaveTextContent('earlier version')
    expect(items[2]).toHaveTextContent('Approved')
    expect(items[2]).toHaveTextContent('Ready to send (sending is simulated)')
    expect(items[2]).toHaveTextContent('Reason—')
  })

  it("labels the supervisor's decisions and lists the rules not evaluated", () => {
    render(
      <DecisionHistory
        inquiryId={7}
        decisions={[
          DELTA_SUBMITTED,
          DELTA_SUPERVISOR_REJECTED,
          {
            ...DELTA_SUPERVISOR_REJECTED,
            action: 'supervisor_approve',
            status_after: 'ready_to_send',
            reason: 'Klient strategiczny',
          },
        ]}
      />,
    )

    const items = within(
      screen.getByRole('region', { name: 'Decision history' }),
    ).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Approved')
    expect(items[0]).toHaveTextContent('Awaiting supervisor approval')
    expect(items[0]).toHaveTextContent(
      'Requires supervisor approval (failing: Margin, Discount, Order value)',
    )
    expect(items[0]).not.toHaveTextContent('not evaluated')
    expect(items[1]).toHaveTextContent('Rejected by supervisor')
    expect(items[1]).toHaveTextContent('Piotr Nowak')
    expect(items[1]).toHaveTextContent('Marża za niska')
    expect(items[1]).toHaveTextContent(
      'Requires supervisor approval (failing: Margin, Discount; not evaluated: Credit)',
    )
    expect(items[2]).toHaveTextContent('Approved by supervisor')
    expect(items[2]).toHaveTextContent('Ready to send (sending is simulated)')
    expect(items[2]).toHaveTextContent('Klient strategiczny')
  })

  it('keeps a decision whose details are no longer readable', () => {
    render(<DecisionHistory inquiryId={7} decisions={[{ ...ACME_APPROVED, snapshot: null }]} />)

    const item = within(screen.getByRole('region', { name: 'Decision history' })).getByRole(
      'listitem',
    )
    expect(item).toHaveTextContent('Approved')
    expect(item).toHaveTextContent('Anna Kowalska')
    expect(item).toHaveTextContent('OfferDetails unavailable')
    expect(item).toHaveTextContent('PolicyDetails unavailable')
  })
})
