import type { TFunction } from 'i18next'
import i18n from '@/i18n'
import type { RuleResult, Signal } from '../api/analysis'

// Codes are selected by the backend producer; original sentences are never parsed.
export const POLICY_REASON_KEYS = {
  margin_threshold_missing: 'business.policy.margin_threshold_missing',
  margin_within_minimum: 'business.policy.margin_within_minimum',
  margin_below_minimum: 'business.policy.margin_below_minimum',
  discount_check_skipped: 'business.policy.discount_check_skipped',
  requested_discount_missing: 'business.policy.requested_discount_missing',
  target_price_missing: 'business.policy.target_price_missing',
  target_list_price_missing: 'business.policy.target_list_price_missing',
  standard_discount_missing: 'business.policy.standard_discount_missing',
  discount_threshold_missing: 'business.policy.discount_threshold_missing',
  requested_discount_within_maximum: 'business.policy.requested_discount_within_maximum',
  requested_discount_above_maximum: 'business.policy.requested_discount_above_maximum',
  target_discount_within_maximum: 'business.policy.target_discount_within_maximum',
  target_discount_above_maximum: 'business.policy.target_discount_above_maximum',
  standard_discount_within_maximum: 'business.policy.standard_discount_within_maximum',
  standard_discount_above_maximum: 'business.policy.standard_discount_above_maximum',
  offered_discount_within_maximum: 'business.policy.offered_discount_within_maximum',
  offered_discount_above_maximum: 'business.policy.offered_discount_above_maximum',
  order_value_threshold_missing: 'business.policy.order_value_threshold_missing',
  order_value_within_maximum: 'business.policy.order_value_within_maximum',
  order_value_above_maximum: 'business.policy.order_value_above_maximum',
  credit_check_skipped: 'business.policy.credit_check_skipped',
  credit_blocked: 'business.policy.credit_blocked',
  credit_data_missing: 'business.policy.credit_data_missing',
  credit_within_limit: 'business.policy.credit_within_limit',
  credit_over_limit: 'business.policy.credit_over_limit',
} as const

function ownKey<T extends object>(keys: T, key: string): key is keyof T & string {
  return Object.hasOwn(keys, key)
}

export function policyReason(rule: RuleResult, t: TFunction): string {
  if (rule.reason_code != null) {
    return ownKey(POLICY_REASON_KEYS, rule.reason_code)
      ? t(POLICY_REASON_KEYS[rule.reason_code])
      : rule.reason
  }
  // An old fail does not tell whether credit was blocked or its limit exceeded,
  // nor which kind of discount decided. Describe only the facts that were stored.
  return t(`business.legacyPolicy.${rule.code}.${rule.verdict}`)
}

const SIGNAL_KEYS = {
  full_coverage: 'business.signal.full_coverage',
  deadline_met: 'business.signal.deadline_met',
  no_deadline: 'business.signal.no_deadline',
  consent_confirmed: 'business.signal.consent_confirmed',
  consent_unconfirmed: 'business.signal.consent_unconfirmed',
  history_accepted: 'business.signal.history_accepted',
  history_declined: 'business.signal.history_declined',
  history_none: 'business.signal.history_none',
  history_mixed: 'business.signal.history_mixed',
  two_sources: 'business.signal.two_sources',
} as const

const CAPABILITY_KEYS = {
  'substitute-compatibility': 'orchestration.capability.substituteCompatibility',
  'substitute-availability': 'orchestration.capability.substituteAvailability',
  'supplier-availability': 'orchestration.capability.supplierAvailability',
  'customer-history': 'orchestration.capability.customerHistory',
} as const
const FIELD_KEYS = {
  customer: 'checks.input.customer',
  product_code: 'checks.input.product_code',
  quantity: 'checks.input.quantity',
} as const
const TASK_KEYS = {
  task_failed: 'business.signal.task_failed',
  not_checked: 'business.signal.not_checked',
  alternative_not_checked: 'business.signal.alternative_not_checked',
} as const

function locale(): string {
  return i18n.resolvedLanguage === 'pl' ? 'pl-PL' : 'en-GB'
}

function quantity(value: string | number | undefined): string | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    ? new Intl.NumberFormat(locale()).format(value)
    : null
}

// Strict calendar date, formatted in UTC so a timezone cannot change the stored day.
function calendarDate(value: string | number | undefined): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return null
  return new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeZone: 'UTC' }).format(date)
}

export function signalMessage(signal: Signal, t: TFunction): string {
  if (ownKey(SIGNAL_KEYS, signal.code)) return t(SIGNAL_KEYS[signal.code])
  const params = signal.params ?? {}
  switch (signal.code) {
    case 'incomplete_coverage': {
      const covered = quantity(params.covered)
      const requested = quantity(params.requested)
      return covered !== null && requested !== null
        ? t('business.signal.incomplete_coverage', { covered, requested })
        : t('business.signal.incomplete_coverage_generic')
    }
    case 'deadline_missed': {
      const fulfilled = calendarDate(params.fulfilled_on)
      const deadline = calendarDate(params.deadline)
      return fulfilled !== null && deadline !== null
        ? t('business.signal.deadline_missed', { fulfilled, deadline })
        : t('business.signal.deadline_missed_generic')
    }
    case 'compat_full':
    case 'compat_partial': {
      const product = params.product_code
      return typeof product === 'string' && product.trim() !== ''
        ? t(`business.signal.${signal.code}`, { product })
        : t(`business.signal.${signal.code}_generic`)
    }
  }
  const [prefix, suffix, extra] = signal.code.split(':')
  if (extra !== undefined || suffix === undefined) return signal.label
  if (prefix === 'uncertain_input' && ownKey(FIELD_KEYS, suffix)) {
    return t('business.signal.uncertain_input', { field: t(FIELD_KEYS[suffix]) })
  }
  if (ownKey(TASK_KEYS, prefix) && ownKey(CAPABILITY_KEYS, suffix)) {
    return t(TASK_KEYS[prefix], { capability: t(CAPABILITY_KEYS[suffix]) })
  }
  return signal.label
}
