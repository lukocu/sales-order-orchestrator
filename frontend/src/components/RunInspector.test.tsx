import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Analysis, OrchestrationView, ParsedFields, RunSummary } from '../api/analysis'
import {
  ACME_ORCHESTRATION,
  COMPATIBILITY_TASK,
  HISTORY_TASK,
  orchestrationRun,
  SUPPLIER_TASK,
} from '../test/orchestrationFixtures'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'
import { ACME_DRAFT } from '../test/replyDraftFixtures'
import i18n from '@/i18n'
import RunInspector from './RunInspector'

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

// One priced LLM step, one deterministic step.
const PARSE_RUN: RunSummary = {
  id: 3,
  status: 'completed',
  started_at: '2026-11-10T09:00:00Z',
  duration_ms: 1520.4,
  steps: [
    {
      id: 10,
      name: 'parse',
      kind: 'llm',
      status: 'ok',
      error_type: null,
      provider: 'groq',
      model: 'openai/gpt-oss-120b',
      input_tokens: 1200,
      output_tokens: 300,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_usd: '0.0003600000',
      price_status: 'priced',
      price_source: 'genai-prices 0.2.1',
      started_at: '2026-11-10T09:00:00Z',
      duration_ms: 1500.2,
    },
    {
      id: 11,
      name: 'resolve-deadline',
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
      started_at: '2026-11-10T09:00:01Z',
      duration_ms: 0.4,
    },
  ],
  totals: {
    input_tokens: 1200,
    output_tokens: 300,
    cache_read_tokens: 0,
    cost_usd: '0.0003600000',
    cost_complete: true,
    steps_duration_ms: 1500.6,
    duration_ms: 1520.4,
  },
}

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    inquiry_id: 7,
    extractor: 'groq',
    reference_date: '2026-11-02',
    fields: FIELDS,
    model_fields: FIELDS,
    uncertain: {},
    corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01Z',
    analyzed_by_name: 'Anna Nowak',
    corrected_at: null,
    corrected_by_name: null,
    run: PARSE_RUN,
    checks: null,
    orchestration: ACME_ORCHESTRATION,
    recommendation: ACME_RECOMMENDATION,
    policy: ACME_POLICY,
    draft: ACME_DRAFT,
    ...overrides,
  }
}

function renderInspector(value: Analysis | null, loading = false) {
  render(<RunInspector analysis={value} loading={loading} open onClose={vi.fn()} />)
  return screen.getByRole('dialog', { name: 'Run inspector' })
}

function section(dialog: HTMLElement, name: string) {
  return within(dialog).getByRole('region', { name })
}

describe('RunInspector', () => {
  it('shows each run with its steps and totals', () => {
    const dialog = renderInspector(analysis())

    const parsing = section(dialog, 'Parsing')
    expect(within(parsing).getByText('Parser: groq')).toBeInTheDocument()
    const table = within(parsing).getByRole('table', { name: 'Steps: Parsing' })
    const [header, parse, resolve, total] = within(table).getAllByRole('row')
    expect(header).toHaveTextContent('Tokens in')
    expect(parse).toHaveTextContent('parse')
    expect(parse).toHaveTextContent('LLM')
    expect(parse).toHaveTextContent('openai/gpt-oss-120b')
    expect(parse).toHaveTextContent('1200')
    expect(parse).toHaveTextContent('$0.00036 list price')
    expect(parse).toHaveTextContent('1500 ms')
    expect(resolve).toHaveTextContent('deterministic')
    expect(resolve).toHaveTextContent('0.4 ms')
    expect(total).toHaveTextContent('Total')
    expect(total).toHaveTextContent('$0.00036 list price')
    expect(total).toHaveTextContent('1520 ms')

    for (const name of ['Orchestration', 'Recommendation', 'Policy', 'Reply draft']) {
      expect(within(section(dialog, name)).getByRole('table')).toBeInTheDocument()
    }
    expect(within(section(dialog, 'Recommendation')).getByText('Recommender: rule-based'))
      .toBeInTheDocument()
  })

  it('shows the plan by stage with parallel tasks and dependencies', () => {
    const dialog = renderInspector(analysis())

    const plan = within(section(dialog, 'Orchestration')).getByRole('region', { name: 'Plan' })
    expect(within(plan).getByText('Planner: fake')).toBeInTheDocument()
    expect(within(plan).getByText(/^Planner summary: Shortage of 30 pcs/)).toBeInTheDocument()

    const first = within(plan).getByRole('list', { name: 'Stage 1 · in parallel' })
    expect(within(first).getAllByRole('listitem')).toHaveLength(3)
    expect(first).toHaveTextContent('catalog-agent')

    const second = within(plan).getByRole('list', { name: 'Stage 2' })
    const [task] = within(second).getAllByRole('listitem')
    expect(task).toHaveTextContent('substitute-availability')
    expect(task).toHaveTextContent('Depends onsubstitute-compatibility')
    expect(task).toHaveTextContent('Attempts1')
    expect(task).toHaveTextContent('Duration1.0 ms')
  })

  it('shows a failed task with its error type and the planner error', () => {
    const orchestration: OrchestrationView = {
      ...ACME_ORCHESTRATION,
      status: 'partial',
      tasks: [
        COMPATIBILITY_TASK,
        {
          ...SUPPLIER_TASK,
          status: 'failed',
          steps: ['agent:supplier-availability', 'agent:supplier-availability'],
          error_type: 'TimeoutError',
          result: null,
        },
        HISTORY_TASK,
      ],
      error: { kind: 'plan_rejected', code: 'missing_prerequisite', message: 'Plan rejected.' },
      run: orchestrationRun([['agent:supplier-availability', 2]]),
    }
    const dialog = renderInspector(analysis({ orchestration }))

    const plan = within(section(dialog, 'Orchestration')).getByRole('region', { name: 'Plan' })
    const failed = within(within(plan).getByRole('list', { name: 'Stage 1 · in parallel' }))
      .getAllByRole('listitem')
      .find((item) => item.textContent?.includes('supplier-availability'))
    expect(failed).toHaveTextContent('Statusfailed')
    expect(failed).toHaveTextContent('Attempts2')
    expect(failed).toHaveTextContent('ErrorTimeoutError')
    expect(within(plan).getByText('Plan rejected: missing_prerequisite')).toBeInTheDocument()
    expect(within(plan).getByRole('list', { name: 'Rejected planner choice' })).toBeInTheDocument()
  })

  it('says when a stage has not run yet', () => {
    const dialog = renderInspector(
      analysis({ recommendation: null, policy: null, draft: undefined }),
    )

    expect(within(section(dialog, 'Checks')).getByText('Not run yet')).toBeInTheDocument()
    expect(within(section(dialog, 'Recommendation')).getByText('Not run yet')).toBeInTheDocument()
    expect(within(section(dialog, 'Reply draft')).queryByRole('table')).not.toBeInTheDocument()
  })

  it('sums every run into a grand total and marks an incomplete cost', () => {
    const unpriced = {
      ...PARSE_RUN.steps[0],
      id: 12,
      name: 'parse-retry',
      cost_usd: null,
      price_status: 'unpriced' as const,
    }
    const run: RunSummary = {
      ...PARSE_RUN,
      steps: [...PARSE_RUN.steps, unpriced],
      totals: { ...PARSE_RUN.totals, cost_complete: false },
    }
    const dialog = renderInspector(analysis({ run }))

    const total = section(dialog, 'Grand total')
    expect(total).toHaveTextContent('Tokens1200 in / 300 out')
    expect(total).toHaveTextContent('Cost$0.00036 list price (some steps not priced)')
    // 1520.4 parsing + 12.4 orchestration + 2.5 recommendation + 1.5 policy + 1.2 draft.
    expect(total).toHaveTextContent('Duration1538 ms')
    const parsing = within(section(dialog, 'Parsing')).getAllByRole('row')
    expect(parsing.at(-2)).toHaveTextContent('not priced')
  })

  it('shows a loading line while the analysis loads', () => {
    renderInspector(null, true)
    expect(screen.getByRole('status')).toHaveTextContent('Loading analysis…')
  })

  it('says when the inquiry has no analysis, without an error', () => {
    const dialog = renderInspector(null)
    expect(
      within(dialog).getByText(
        'This inquiry has not been analysed yet, so there are no runs to show.',
      ),
    ).toBeInTheDocument()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('is in English in tests and follows the language switch', async () => {
    const dialog = renderInspector(analysis())
    expect(within(dialog).getByRole('button', { name: 'Close' })).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: 'Grand total' })).toBeInTheDocument()

    await i18n.changeLanguage('pl')

    expect(
      await screen.findByRole('dialog', { name: 'Inspektor przebiegu' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Zamknij' })).toBeInTheDocument()
  })
})
