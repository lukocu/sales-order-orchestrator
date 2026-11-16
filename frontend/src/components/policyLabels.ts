import type { TFunction } from 'i18next'
import type { PolicyOutcome, RuleCode, RuleResult, RuleVerdict } from '../api/analysis'
import { formatPercent, formatPln } from './format'

// Every verdict is shown as text; the tone only adds the colour.
export type PolicyTone = 'ok' | 'warn' | 'error'

// Labels are i18n keys, resolved with t() at render time.
export const OUTCOME_LABEL = {
  no_approval_needed: { key: 'policy.outcome.no_approval_needed', tone: 'ok' },
  requires_supervisor: {
    key: 'policy.outcome.requires_supervisor',
    tone: 'warn',
  },
} as const satisfies Record<PolicyOutcome, { key: string; tone: PolicyTone }>

export const RULE_LABEL = {
  margin: 'policy.rule.margin',
  discount: 'policy.rule.discount',
  order_value: 'policy.rule.order_value',
  credit: 'policy.rule.credit',
} as const satisfies Record<RuleCode, string>

export const VERDICT_LABEL = {
  pass: { key: 'policy.verdict.pass', tone: 'ok' },
  fail: { key: 'policy.verdict.fail', tone: 'error' },
  not_evaluated: { key: 'policy.verdict.not_evaluated', tone: 'warn' },
} as const satisfies Record<RuleVerdict, { key: string; tone: PolicyTone }>

// How the actual value must compare with the threshold to pass.
const COMPARATOR: Record<RuleCode, string> = {
  margin: '≥',
  discount: '≤',
  order_value: '≤',
  credit: '≤',
}

export function ruleAmount(rule: RuleResult, value: string | null): string {
  if (value === null) return '—'
  return rule.unit === 'percent' ? formatPercent(value) : formatPln(value)
}

export function thresholdText(rule: RuleResult, t: TFunction): string {
  if (rule.threshold === null) return '—'
  const text = `${COMPARATOR[rule.code]} ${ruleAmount(rule, rule.threshold)}`
  return rule.code === 'credit' ? t('policy.creditThreshold', { threshold: text }) : text
}

// True when the policy stage has no current verdict although the recommendation allows one:
// re-running it is then the way forward.
export function policyRerunOffered(
  policy: { stale: boolean } | null,
  recommendation: { status: string; stale: boolean } | null,
): boolean {
  const blocked =
    recommendation === null || recommendation.status === 'failed' || recommendation.stale
  return !blocked && (policy === null || policy.stale)
}
