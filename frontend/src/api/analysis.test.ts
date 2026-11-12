import { describe, expect, it, vi } from 'vitest'
import {
  ACME_ORCHESTRATION,
  DELTA_ORCHESTRATION,
  OMEGA_ORCHESTRATION,
} from '../test/orchestrationFixtures'
import { ACME_POLICY, CREDIT_NOT_EVALUATED, DELTA_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION, DELTA_RECOMMENDATION } from '../test/recommendationFixtures'
import {
  ACME_APPROVED,
  ACME_DRAFT,
  ACME_EDITED,
  ACME_EDITED_DRAFT,
  ACME_REJECTED_EARLIER,
  DELTA_DRAFT,
} from '../test/replyDraftFixtures'
import {
  decideDraft,
  DRAFT_CHANGED,
  editDraft,
  isOrchestrationView,
  isPolicyView,
  isRecommendationView,
  isReplyDraftDecision,
  isReplyDraftView,
  regenerateDraft,
  rerunOrchestration,
  rerunPolicy,
  rerunRecommendation,
  type Analysis,
} from './analysis'
import { ApiError } from './client'

// JSON round trip, as the view arrives from the API.
function wire(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value))
}

const ANALYSIS: Analysis = {
  inquiry_id: 7,
  extractor: 'fake',
  reference_date: '2026-11-02',
  fields: {
    customer: 'ACME',
    product_code: 'ABC-100',
    quantity: 80,
    deadline: '2026-11-06',
    deadline_text: 'do piątku',
    substitute_allowed: true,
    price_kind: 'none',
    price_value: null,
    price_text: null,
  },
  model_fields: {
    customer: 'ACME',
    product_code: 'ABC-100',
    quantity: 80,
    deadline: '2026-11-06',
    deadline_text: 'do piątku',
    substitute_allowed: true,
    price_kind: 'none',
    price_value: null,
    price_text: null,
  },
  uncertain: {},
  corrected_fields: [],
  analyzed_at: '2026-11-10T09:00:01Z',
  analyzed_by_name: null,
  corrected_at: null,
  corrected_by_name: null,
  run: null,
  checks: null,
  orchestration: ACME_ORCHESTRATION,
}

function stubFetch(body: unknown) {
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('isOrchestrationView', () => {
  it.each([
    ['ACME', ACME_ORCHESTRATION],
    ['Omega', OMEGA_ORCHESTRATION],
    ['Delta', DELTA_ORCHESTRATION],
  ])('accepts the %s view', (_, view) => {
    expect(isOrchestrationView(wire(view))).toBe(true)
  })

  it('accepts a failed view with its error and without a run', () => {
    const view = {
      ...ACME_ORCHESTRATION,
      status: 'failed',
      tasks: [],
      run: null,
      error: { kind: 'plan_rejected', code: 'too_many_tasks', message: 'Too many tasks' },
    }
    expect(isOrchestrationView(wire(view))).toBe(true)
  })

  it.each([
    ['an unknown status', { ...ACME_ORCHESTRATION, status: 'done' }],
    ['an unknown consent', { ...ACME_ORCHESTRATION, consent: 'maybe' }],
    [
      'an unknown task capability',
      {
        ...ACME_ORCHESTRATION,
        tasks: [{ ...ACME_ORCHESTRATION.tasks[0], capability: 'price-check' }],
      },
    ],
    [
      'an unknown task status',
      { ...ACME_ORCHESTRATION, tasks: [{ ...ACME_ORCHESTRATION.tasks[0], status: 'running' }] },
    ],
    [
      'an unknown result capability',
      {
        ...ACME_ORCHESTRATION,
        tasks: [
          {
            ...ACME_ORCHESTRATION.tasks[0],
            result: { capability: 'price-check', candidates: [] },
          },
        ],
      },
    ],
    [
      'a result whose fields do not match its capability',
      {
        ...ACME_ORCHESTRATION,
        tasks: [
          {
            ...ACME_ORCHESTRATION.tasks[0],
            result: { capability: 'supplier-availability', candidates: [] },
          },
        ],
      },
    ],
    [
      'an unknown planner choice capability',
      {
        ...ACME_ORCHESTRATION,
        planner_choice: { tasks: [{ capability: 'price-check', reason: 'x' }], summary: 's' },
      },
    ],
    [
      'an unknown error kind',
      { ...ACME_ORCHESTRATION, error: { kind: 'timeout', code: 'x', message: 'x' } },
    ],
  ])('rejects %s', (_, view) => {
    expect(isOrchestrationView(wire(view))).toBe(false)
  })
})

describe('rerunOrchestration', () => {
  it('posts to the orchestration endpoint and returns the analysis', async () => {
    const fetchMock = stubFetch(ANALYSIS)

    await expect(rerunOrchestration(7)).resolves.toEqual(ANALYSIS)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/inquiries/7/orchestration',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('rejects an analysis whose orchestration has an unknown status', async () => {
    stubFetch({ ...ANALYSIS, orchestration: { ...ACME_ORCHESTRATION, status: 'done' } })

    await expect(rerunOrchestration(7)).rejects.toThrow('Invalid response body')
  })
})

describe('isRecommendationView', () => {
  it.each([
    ['ACME', ACME_RECOMMENDATION],
    ['Delta', DELTA_RECOMMENDATION],
  ])('accepts the %s view', (_, view) => {
    expect(isRecommendationView(wire(view))).toBe(true)
  })

  it('accepts a failed view with its error, a rejected choice and without a run', () => {
    const view = {
      ...ACME_RECOMMENDATION,
      status: 'failed',
      run: null,
      error: { kind: 'choice_rejected', code: 'foreign_signal', message: 'Foreign signal' },
    }
    expect(isRecommendationView(wire(view))).toBe(true)
  })

  const option = ACME_RECOMMENDATION.options[0]
  it.each([
    ['an unknown status', { ...ACME_RECOMMENDATION, status: 'partial' }],
    ['a missing stale flag', { ...ACME_RECOMMENDATION, stale: undefined }],
    ['an unknown option kind', { ...ACME_RECOMMENDATION, options: [{ ...option, kind: 'x' }] }],
    ['an unknown band', { ...ACME_RECOMMENDATION, options: [{ ...option, band: 'VERY_HIGH' }] }],
    ['a numeric margin', { ...ACME_RECOMMENDATION, options: [{ ...option, margin_percent: 26 }] }],
    [
      'an unknown line source',
      {
        ...ACME_RECOMMENDATION,
        options: [{ ...option, lines: [{ ...option.lines[0], source: 'warehouse' }] }],
      },
    ],
    [
      'an unknown signal polarity',
      {
        ...ACME_RECOMMENDATION,
        options: [{ ...option, signals: [{ code: 'x', polarity: 'neutral', label: 'x' }] }],
      },
    ],
    [
      'cited signals that are not a list of codes',
      { ...ACME_RECOMMENDATION, choice: { ...ACME_RECOMMENDATION.choice, cited_signals: 'x' } },
    ],
    [
      'an unknown error kind',
      { ...ACME_RECOMMENDATION, error: { kind: 'timeout', code: 'x', message: 'x' } },
    ],
  ])('rejects %s', (_, view) => {
    expect(isRecommendationView(wire(view))).toBe(false)
  })
})

describe('rerunRecommendation', () => {
  const analysis = { ...ANALYSIS, recommendation: ACME_RECOMMENDATION }

  it('posts to the recommendation endpoint and returns the analysis', async () => {
    const fetchMock = stubFetch(analysis)

    await expect(rerunRecommendation(7)).resolves.toEqual(analysis)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/inquiries/7/recommendation',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('accepts an older analysis without the recommendation field', async () => {
    stubFetch(ANALYSIS)

    await expect(rerunRecommendation(7)).resolves.toEqual(ANALYSIS)
  })

  it('rejects an analysis whose recommendation has an unknown band', async () => {
    stubFetch({
      ...analysis,
      recommendation: {
        ...ACME_RECOMMENDATION,
        options: [{ ...ACME_RECOMMENDATION.options[0], band: 'SURE' }],
      },
    })

    await expect(rerunRecommendation(7)).rejects.toThrow('Invalid response body')
  })
})

describe('isPolicyView', () => {
  it.each([
    ['ACME', ACME_POLICY],
    ['Delta', DELTA_POLICY],
  ])('accepts the %s view', (_, view) => {
    expect(isPolicyView(wire(view))).toBe(true)
  })

  it('accepts a not evaluated rule without values and a view without a run', () => {
    const view = {
      ...DELTA_POLICY,
      rules: [...DELTA_POLICY.rules.slice(0, 3), CREDIT_NOT_EVALUATED],
      run: null,
    }
    expect(isPolicyView(wire(view))).toBe(true)
  })

  const rule = ACME_POLICY.rules[0]
  it.each([
    ['an unknown outcome', { ...ACME_POLICY, outcome: 'approved' }],
    ['a missing stale flag', { ...ACME_POLICY, stale: undefined }],
    ['a missing examples flag', { ...ACME_POLICY, thresholds_are_examples: undefined }],
    ['rules that are not a list', { ...ACME_POLICY, rules: rule }],
    ['an unknown rule code', { ...ACME_POLICY, rules: [{ ...rule, code: 'stock' }] }],
    ['an unknown verdict', { ...ACME_POLICY, rules: [{ ...rule, verdict: 'warn' }] }],
    ['an unknown unit', { ...ACME_POLICY, rules: [{ ...rule, unit: 'EUR' }] }],
    ['a numeric actual value', { ...ACME_POLICY, rules: [{ ...rule, actual: 25.51 }] }],
    ['a missing reason', { ...ACME_POLICY, rules: [{ ...rule, reason: undefined }] }],
  ])('rejects %s', (_, view) => {
    expect(isPolicyView(wire(view))).toBe(false)
  })
})

describe('rerunPolicy', () => {
  const analysis = { ...ANALYSIS, recommendation: ACME_RECOMMENDATION, policy: ACME_POLICY }

  it('posts to the policy endpoint and returns the analysis', async () => {
    const fetchMock = stubFetch(analysis)

    await expect(rerunPolicy(7)).resolves.toEqual(analysis)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/inquiries/7/policy',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('accepts an older analysis without the policy field', async () => {
    const older = { ...ANALYSIS, recommendation: ACME_RECOMMENDATION }
    stubFetch(older)

    await expect(rerunPolicy(7)).resolves.toEqual(older)
  })

  it('accepts an analysis without a verdict', async () => {
    const none = { ...analysis, policy: null }
    stubFetch(none)

    await expect(rerunPolicy(7)).resolves.toEqual(none)
  })

  it('rejects an analysis whose policy has an unknown verdict', async () => {
    stubFetch({
      ...analysis,
      policy: { ...ACME_POLICY, rules: [{ ...ACME_POLICY.rules[0], verdict: 'ok' }] },
    })

    await expect(rerunPolicy(7)).rejects.toThrow('Invalid response body')
  })
})

describe('isReplyDraftView', () => {
  it.each([
    ['ACME', ACME_DRAFT],
    ['ACME edited', ACME_EDITED_DRAFT],
    ['Delta', DELTA_DRAFT],
  ])('accepts the %s view', (_, view) => {
    expect(isReplyDraftView(wire(view))).toBe(true)
  })

  it('accepts a draft without a verdict, a why or a run', () => {
    const view = { ...ACME_DRAFT, policy: null, why: null, run: null, text_source: 'fallback' }
    expect(isReplyDraftView(wire(view))).toBe(true)
  })

  const line = ACME_DRAFT.offer.lines[0]
  it.each([
    ['an unknown status', { ...ACME_DRAFT, status: 'sent' }],
    ['an unknown text source', { ...ACME_DRAFT, text_source: 'llm' }],
    ['a missing stale flag', { ...ACME_DRAFT, stale: undefined }],
    ['a missing token', { ...ACME_DRAFT, updated_at: undefined }],
    [
      'a missing edited flag',
      { ...ACME_DRAFT, offer: { ...ACME_DRAFT.offer, edited: undefined } },
    ],
    [
      'a numeric unit price',
      { ...ACME_DRAFT, offer: { ...ACME_DRAFT.offer, lines: [{ ...line, unit_price: 114 }] } },
    ],
    [
      'a line without a list price',
      {
        ...ACME_DRAFT,
        offer: { ...ACME_DRAFT.offer, lines: [{ ...line, list_price: undefined }] },
      },
    ],
    [
      'an unknown verdict outcome',
      { ...ACME_DRAFT, policy: { ...ACME_DRAFT.policy, outcome: 'ok' } },
    ],
    ['signals that are not labels', { ...ACME_DRAFT, why: { justification: 'x', signals: [1] } }],
  ])('rejects %s', (_, view) => {
    expect(isReplyDraftView(wire(view))).toBe(false)
  })
})

describe('isReplyDraftDecision', () => {
  it.each([
    ['an approval', ACME_APPROVED],
    ['an edit', ACME_EDITED],
    ['an earlier rejection', ACME_REJECTED_EARLIER],
  ])('accepts %s', (_, decision) => {
    expect(isReplyDraftDecision(wire(decision))).toBe(true)
  })

  it('accepts a decision without a verdict and an unknown user', () => {
    const decision = {
      ...ACME_APPROVED,
      decided_by_name: null,
      snapshot: { ...ACME_APPROVED.snapshot, policy_outcome: null },
    }
    expect(isReplyDraftDecision(wire(decision))).toBe(true)
  })

  it.each([
    ['an unknown action', { ...ACME_APPROVED, action: 'send' }],
    ['an unknown status after', { ...ACME_APPROVED, status_after: 'sent' }],
    ['a missing current flag', { ...ACME_APPROVED, current: undefined }],
    [
      'an unknown failing rule',
      { ...ACME_APPROVED, snapshot: { ...ACME_APPROVED.snapshot, failing_rules: ['stock'] } },
    ],
  ])('rejects %s', (_, decision) => {
    expect(isReplyDraftDecision(wire(decision))).toBe(false)
  })
})

describe('reply draft helpers', () => {
  const analysis = {
    ...ANALYSIS,
    recommendation: ACME_RECOMMENDATION,
    policy: ACME_POLICY,
    draft: ACME_DRAFT,
    decisions: [ACME_REJECTED_EARLIER],
  }

  it('regenerates the draft with a POST and returns the analysis', async () => {
    const fetchMock = stubFetch(analysis)

    await expect(regenerateDraft(7)).resolves.toEqual(analysis)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/inquiries/7/draft',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('puts an edit with the token of the draft it was made on', async () => {
    const fetchMock = stubFetch(analysis)
    const edit = {
      option_id: 'stock',
      lines: [{ product_code: 'ABC-100', quantity: 50, unit_price: '100.00' }],
      reason: 'Negocjacje',
    }

    await expect(editDraft(7, ACME_DRAFT.updated_at, edit)).resolves.toEqual(analysis)
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(path).toBe('/api/inquiries/7/draft')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(String(init.body))).toEqual({ updated_at: ACME_DRAFT.updated_at, ...edit })
  })

  it('posts a decision with its reason', async () => {
    const fetchMock = stubFetch(analysis)

    await expect(decideDraft(7, ACME_DRAFT.updated_at, 'reject', 'Za drogo')).resolves.toEqual(
      analysis,
    )
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(path).toBe('/api/inquiries/7/draft/decision')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      updated_at: ACME_DRAFT.updated_at,
      action: 'reject',
      reason: 'Za drogo',
    })
  })

  it('accepts an older analysis without the draft and decisions fields', async () => {
    const older = { ...ANALYSIS, recommendation: ACME_RECOMMENDATION, policy: ACME_POLICY }
    stubFetch(older)

    await expect(regenerateDraft(7)).resolves.toEqual(older)
  })

  it('rejects an analysis whose decisions are not a list', async () => {
    stubFetch({ ...analysis, decisions: ACME_APPROVED })

    await expect(regenerateDraft(7)).rejects.toThrow('Invalid response body')
  })

  it('rejects a changed draft as a 409 with the reload detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: DRAFT_CHANGED }), {
            status: 409,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )

    const failure = decideDraft(7, ACME_DRAFT.updated_at, 'approve', null)
    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status: 409, message: 'Draft changed, reload' })
  })
})
