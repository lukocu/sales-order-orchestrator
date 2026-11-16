import { describe, expect, it } from 'vitest'
import type { Analysis, ChecksView, ParsedFields } from '../api/analysis'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'
import { ACME_DRAFT, DELTA_AWAITING } from '../test/replyDraftFixtures'
import { inquirySteps, stepBackReason, type StepId, type StepState } from './inquirySteps'

const FIELDS: ParsedFields = {
  customer: 'ACME',
  product_code: 'ABC-100',
  quantity: 80,
  deadline: null,
  deadline_text: null,
  substitute_allowed: true,
  price_kind: 'none',
  price_value: null,
  price_text: null,
}

// Only the fields the step model reads are filled in.
const EXCEPTION = {
  outcome: 'exception',
  exception_type: 'insufficient_stock',
  reasons: [],
  checked_at: '2026-11-10T09:00:02Z',
  stale: false,
  uncertain_inputs: [],
  run: null,
} as unknown as ChecksView

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
    analyzed_by_name: null,
    corrected_at: null,
    corrected_by_name: null,
    run: null,
    checks: null,
    orchestration: null,
    ...overrides,
  }
}

// An exception carried all the way to a reply draft.
const DRAFTED: Partial<Analysis> = {
  checks: EXCEPTION,
  orchestration: ACME_ORCHESTRATION,
  recommendation: ACME_RECOMMENDATION,
  policy: ACME_POLICY,
  draft: ACME_DRAFT,
}

function states(
  inquiry: StepState,
  variants: StepState,
  approval: StepState,
  reply: StepState,
): Record<StepId, StepState> {
  return { inquiry, variants, approval, reply }
}

describe('inquirySteps', () => {
  it.each<[string, Analysis | null, StepId, Record<StepId, StepState>]>([
    ['not analysed', null, 'inquiry', states('active', 'locked', 'locked', 'locked')],
    ['no check result', analysis(), 'inquiry', states('active', 'locked', 'locked', 'locked')],
    [
      'stale check result',
      analysis({ ...DRAFTED, checks: { ...EXCEPTION, stale: true } }),
      'inquiry',
      states('active', 'locked', 'locked', 'locked'),
    ],
    [
      'needs input',
      analysis({ checks: { ...EXCEPTION, outcome: 'needs_input' } }),
      'inquiry',
      states('active', 'locked', 'locked', 'locked'),
    ],
    [
      'standard',
      analysis({ checks: { ...EXCEPTION, outcome: 'standard' } }),
      'inquiry',
      states('done', 'not_needed', 'not_needed', 'not_needed'),
    ],
    [
      'exception without orchestration',
      analysis({ checks: EXCEPTION }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'exception with a failed orchestration',
      analysis({
        ...DRAFTED,
        orchestration: { ...ACME_ORCHESTRATION, status: 'failed' },
      }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'exception with a partial orchestration',
      analysis({
        ...DRAFTED,
        orchestration: { ...ACME_ORCHESTRATION, status: 'partial' },
      }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'exception without a recommendation',
      analysis({ checks: EXCEPTION, orchestration: ACME_ORCHESTRATION }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'failed recommendation',
      analysis({ ...DRAFTED, recommendation: { ...ACME_RECOMMENDATION, status: 'failed' } }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'stale recommendation',
      analysis({ ...DRAFTED, recommendation: { ...ACME_RECOMMENDATION, stale: true } }),
      'variants',
      states('done', 'active', 'locked', 'locked'),
    ],
    [
      'current recommendation without a draft',
      analysis({ ...DRAFTED, policy: null, draft: null }),
      'approval',
      states('done', 'done', 'active', 'locked'),
    ],
    [
      'stale draft',
      analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, stale: true } }),
      'approval',
      states('done', 'done', 'active', 'locked'),
    ],
    ['draft', analysis(DRAFTED), 'approval', states('done', 'done', 'active', 'locked')],
    [
      'awaiting supervisor',
      analysis({ ...DRAFTED, draft: DELTA_AWAITING }),
      'approval',
      states('done', 'done', 'active', 'locked'),
    ],
    [
      'rejected',
      analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, status: 'rejected' } }),
      'approval',
      states('done', 'done', 'active', 'locked'),
    ],
    [
      'ready to send',
      analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, status: 'ready_to_send' } }),
      'reply',
      states('done', 'done', 'done', 'active'),
    ],
    [
      'ready to send but stale',
      analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, status: 'ready_to_send', stale: true } }),
      'approval',
      states('done', 'done', 'active', 'locked'),
    ],
  ])('%s', (_name, input, active, expected) => {
    expect(inquirySteps(input)).toEqual({ active, states: expected })
  })
})

describe('stepBackReason', () => {
  const rejected = analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, status: 'rejected' } })

  it('names a rejected draft although the flow stays at the approval step', () => {
    expect(stepBackReason(analysis(DRAFTED), rejected)).toBe('steps.back.draftRejected')
  })

  it('does not repeat the reason while the draft stays rejected', () => {
    expect(stepBackReason(rejected, rejected)).toBeNull()
  })

  it('names a replaced analysis', () => {
    const replaced = analysis({ analyzed_at: '2026-11-10T10:00:00Z' })
    expect(stepBackReason(analysis(DRAFTED), replaced)).toBe('steps.back.analysisReplaced')
  })

  it.each([
    ['stale checks', analysis({ ...DRAFTED, checks: { ...EXCEPTION, stale: true } })],
    [
      'a stale recommendation',
      analysis({ ...DRAFTED, recommendation: { ...ACME_RECOMMENDATION, stale: true } }),
    ],
  ])('names an outdated result: %s', (_name, next) => {
    expect(stepBackReason(analysis(DRAFTED), next)).toBe('steps.back.outdated')
  })

  it('is null when the flow moves forward or stays', () => {
    const ready = analysis({ ...DRAFTED, draft: { ...ACME_DRAFT, status: 'ready_to_send' } })
    expect(stepBackReason(analysis(DRAFTED), ready)).toBeNull()
    expect(stepBackReason(analysis(DRAFTED), analysis(DRAFTED))).toBeNull()
  })

  it('is null without a previous or a next analysis', () => {
    expect(stepBackReason(null, analysis(DRAFTED))).toBeNull()
    expect(stepBackReason(analysis(DRAFTED), null)).toBeNull()
  })
})
