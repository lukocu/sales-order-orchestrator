import type { OrchestrationView, RunSummary, StepSummary, TaskOutcome } from '../api/analysis'

// Orchestration results of the seed inquiries with the fake planner, as the API returns them.

function step(id: number, name: string, durationMs: number): StepSummary {
  return {
    id,
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
    started_at: '2026-11-10T09:00:03Z',
    duration_ms: durationMs,
  }
}

export function orchestrationRun(agentSteps: [string, number][]): RunSummary {
  const steps = [
    step(30, 'plan', 0.5),
    step(31, 'validate-plan', 0.2),
    step(32, 'match-capabilities', 0.1),
    ...agentSteps.map(([name, ms], index) => step(33 + index, name, ms)),
  ]
  const sum = steps.reduce((total, item) => total + item.duration_ms, 0)
  return {
    id: 5,
    status: 'completed',
    started_at: '2026-11-10T09:00:03Z',
    duration_ms: 12.4,
    steps,
    totals: {
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cost_usd: '0',
      cost_complete: true,
      steps_duration_ms: sum,
      duration_ms: 12.4,
    },
  }
}

export const COMPATIBILITY_TASK: TaskOutcome = {
  capability: 'substitute-compatibility',
  agent: 'catalog-agent',
  reason: 'ABC-100 is short by 30 pcs; look for compatible substitutes.',
  depends_on: [],
  stage: 1,
  status: 'completed',
  steps: ['agent:substitute-compatibility'],
  error_type: null,
  result: {
    capability: 'substitute-compatibility',
    candidates: [
      {
        code: 'ABC-110',
        name: 'Czujnik ciśnienia ABC-110',
        compatibility: 'full',
        note: 'Same range',
      },
    ],
  },
}

export const SUPPLIER_TASK: TaskOutcome = {
  capability: 'supplier-availability',
  agent: 'supplier-agent',
  reason: 'Check whether a supplier can deliver 30 pcs of ABC-100 before the deadline.',
  depends_on: [],
  stage: 1,
  status: 'completed',
  steps: ['agent:supplier-availability'],
  error_type: null,
  result: {
    capability: 'supplier-availability',
    offers: [
      {
        supplier: 'Sensor Parts',
        quantity: 200,
        lead_time_days: 7,
        available_on: '2026-11-09',
        meets_deadline: false,
        covers_shortage: true,
      },
    ],
  },
}

export const HISTORY_TASK: TaskOutcome = {
  capability: 'customer-history',
  agent: 'history-agent',
  reason: 'Check whether the customer accepted substitutes before.',
  depends_on: [],
  stage: 1,
  status: 'completed',
  steps: ['agent:customer-history'],
  error_type: null,
  result: {
    capability: 'customer-history',
    orders_count: 3,
    substitutes_offered: 2,
    substitutes_accepted: 2,
    signal: 'accepted_before',
  },
}

export const AVAILABILITY_TASK: TaskOutcome = {
  capability: 'substitute-availability',
  agent: 'warehouse-agent',
  reason: 'Check whether substitute stock covers the shortage of 30 pcs.',
  depends_on: ['substitute-compatibility'],
  stage: 2,
  status: 'completed',
  steps: ['agent:substitute-availability'],
  error_type: null,
  result: {
    capability: 'substitute-availability',
    candidates: [{ code: 'ABC-110', stock: 40, covers_shortage: true }],
  },
}

const ACME_TASKS = [COMPATIBILITY_TASK, SUPPLIER_TASK, HISTORY_TASK, AVAILABILITY_TASK]

// ACME, 80 × ABC-100 with 50 in stock, substitute allowed.
export const ACME_ORCHESTRATION: OrchestrationView = {
  status: 'completed',
  consent: 'confirmed',
  planner: 'fake',
  planner_choice: {
    tasks: ACME_TASKS.map(({ capability, reason }) => ({ capability, reason })),
    summary:
      'Shortage of 30 pcs of ABC-100; substitute consent is confirmed, so substitutes, ' +
      'supplier delivery and order history are checked.',
  },
  planner_steps: ['plan'],
  tasks: ACME_TASKS,
  error: null,
  orchestrated_at: '2026-11-10T09:00:03Z',
  stale: false,
  run: orchestrationRun([
    ['agent:substitute-compatibility', 1.5],
    ['agent:supplier-availability', 2.5],
    ['agent:customer-history', 3],
    ['agent:substitute-availability', 1],
  ]),
}

// Technika Omega, 120 × XYZ-300 with 60 in stock, substitute refused.
const OMEGA_TASKS: TaskOutcome[] = [
  {
    ...SUPPLIER_TASK,
    reason: 'Check whether a supplier can deliver 60 pcs of XYZ-300 before the deadline.',
    result: {
      capability: 'supplier-availability',
      offers: [
        {
          supplier: 'Valve Works',
          quantity: 80,
          lead_time_days: 5,
          available_on: '2026-11-10',
          meets_deadline: true,
          covers_shortage: true,
        },
      ],
    },
  },
  {
    ...HISTORY_TASK,
    result: {
      capability: 'customer-history',
      orders_count: 2,
      substitutes_offered: 1,
      substitutes_accepted: 0,
      signal: 'declined_before',
    },
  },
]

export const OMEGA_ORCHESTRATION: OrchestrationView = {
  ...ACME_ORCHESTRATION,
  consent: 'refused',
  planner_choice: {
    tasks: OMEGA_TASKS.map(({ capability, reason }) => ({ capability, reason })),
    summary:
      'Shortage of 60 pcs of XYZ-300; the customer refused substitutes, so only supplier ' +
      'delivery and order history are checked.',
  },
  tasks: OMEGA_TASKS,
  run: orchestrationRun([
    ['agent:supplier-availability', 2],
    ['agent:customer-history', 2],
  ]),
}

// Hurtownia Delta, 500 × ABC-100 with 50 in stock, substitute not stated, no deadline.
const DELTA_TASKS: TaskOutcome[] = [
  COMPATIBILITY_TASK,
  {
    ...SUPPLIER_TASK,
    result: {
      capability: 'supplier-availability',
      offers: [
        {
          supplier: 'Sensor Parts',
          quantity: 200,
          lead_time_days: 7,
          available_on: '2026-11-09',
          meets_deadline: null,
          covers_shortage: false,
        },
      ],
    },
  },
  {
    ...HISTORY_TASK,
    result: {
      capability: 'customer-history',
      orders_count: 0,
      substitutes_offered: 0,
      substitutes_accepted: 0,
      signal: 'no_substitute_history',
    },
  },
  {
    ...AVAILABILITY_TASK,
    result: {
      capability: 'substitute-availability',
      candidates: [{ code: 'ABC-110', stock: 40, covers_shortage: false }],
    },
  },
]

export const DELTA_ORCHESTRATION: OrchestrationView = {
  ...ACME_ORCHESTRATION,
  consent: 'unconfirmed',
  tasks: DELTA_TASKS,
}
