import { describe, expect, it, vi } from 'vitest'
import {
  ACME_ORCHESTRATION,
  DELTA_ORCHESTRATION,
  OMEGA_ORCHESTRATION,
} from '../test/orchestrationFixtures'
import { isOrchestrationView, rerunOrchestration, type Analysis } from './analysis'

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
