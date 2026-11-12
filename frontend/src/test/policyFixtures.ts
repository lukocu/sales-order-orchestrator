import type { PolicyView, RuleResult, RunSummary } from '../api/analysis'

// Policy verdicts of the seed inquiries with the rule-based recommender and the example
// thresholds of migration 0011 (margin ≥ 20%, discount ≤ 15%, order value ≤ 30000 PLN), as
// the API returns them.

export function policyRun(): RunSummary {
  return {
    id: 8,
    status: 'completed',
    started_at: '2026-11-10T09:00:05Z',
    duration_ms: 1.5,
    steps: [
      {
        id: 50,
        name: 'rules',
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
        started_at: '2026-11-10T09:00:05Z',
        duration_ms: 0.4,
      },
    ],
    totals: {
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cost_usd: '0',
      cost_complete: true,
      steps_duration_ms: 0.4,
      duration_ms: 1.5,
    },
  }
}

// ACME: the substitute option (9262.50 PLN, margin 25.51%), standard discount 5%, balance
// 2000 of a 30000 limit.
export const ACME_POLICY: PolicyView = {
  option_id: 'stock+ABC-110',
  rules: [
    {
      code: 'margin',
      verdict: 'pass',
      actual: '25.51',
      threshold: '20.00',
      unit: 'percent',
      reason: 'Margin at or above the minimum',
    },
    {
      code: 'discount',
      verdict: 'pass',
      actual: '5.00',
      threshold: '15.00',
      unit: 'percent',
      reason: 'Standard discount within the maximum',
    },
    {
      code: 'order_value',
      verdict: 'pass',
      actual: '9262.50',
      threshold: '30000.00',
      unit: 'PLN',
      reason: 'Order value within the maximum',
    },
    {
      code: 'credit',
      verdict: 'pass',
      actual: '11262.50',
      threshold: '30000.00',
      unit: 'PLN',
      reason: 'Balance + selected option value within limit',
    },
  ],
  outcome: 'no_approval_needed',
  thresholds_are_examples: true,
  evaluated_at: '2026-11-10T09:00:05Z',
  stale: false,
  run: policyRun(),
}

// Hurtownia Delta: the combined option (31500.00 PLN, margin 14.29%), a requested 25% discount,
// balance 0 of a 50000 limit.
export const DELTA_POLICY: PolicyView = {
  option_id: 'stock+ABC-110+supplier:Sensortech Polska',
  rules: [
    {
      code: 'margin',
      verdict: 'fail',
      actual: '14.29',
      threshold: '20.00',
      unit: 'percent',
      reason: 'Margin below the minimum',
    },
    {
      code: 'discount',
      verdict: 'fail',
      actual: '25',
      threshold: '15.00',
      unit: 'percent',
      reason: 'Requested discount above the maximum',
    },
    {
      code: 'order_value',
      verdict: 'fail',
      actual: '31500.00',
      threshold: '30000.00',
      unit: 'PLN',
      reason: 'Order value above the maximum',
    },
    {
      code: 'credit',
      verdict: 'pass',
      actual: '31500.00',
      threshold: '50000.00',
      unit: 'PLN',
      reason: 'Balance + selected option value within limit',
    },
  ],
  outcome: 'requires_supervisor',
  thresholds_are_examples: true,
  evaluated_at: '2026-11-10T09:00:05Z',
  stale: false,
  run: policyRun(),
}

// A credit check skipped (no customer limit): the rule cannot be evaluated.
export const CREDIT_NOT_EVALUATED: RuleResult = {
  code: 'credit',
  verdict: 'not_evaluated',
  actual: null,
  threshold: null,
  unit: 'PLN',
  reason: 'Credit check skipped',
}
