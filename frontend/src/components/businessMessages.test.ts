import { describe, expect, it } from 'vitest'
import i18n from '@/i18n'
import en from '../i18n/locales/en.json'
import pl from '../i18n/locales/pl.json'
import type { RuleCode, RuleResult, RuleVerdict, Signal } from '../api/analysis'
import { POLICY_REASON_KEYS, policyReason, signalMessage } from './businessMessages'

const RULE: RuleResult = {
  code: 'discount', verdict: 'fail', actual: '25', threshold: '15', unit: 'percent',
  reason: 'An original business explanation',
}
function signal(code: string, params?: Signal['params']): Signal {
  return { code, polarity: 'risk', label: 'An original business signal', ...(params === undefined ? {} : { params }) }
}

// This catalogue is the producer contract, independent from the formatter's lookup.
const REASON_CODES = [
  'margin_threshold_missing', 'margin_within_minimum', 'margin_below_minimum',
  'discount_check_skipped', 'requested_discount_missing', 'target_price_missing',
  'target_list_price_missing', 'standard_discount_missing', 'discount_threshold_missing',
  'requested_discount_within_maximum', 'requested_discount_above_maximum',
  'target_discount_within_maximum', 'target_discount_above_maximum',
  'standard_discount_within_maximum', 'standard_discount_above_maximum',
  'offered_discount_within_maximum', 'offered_discount_above_maximum',
  'order_value_threshold_missing', 'order_value_within_maximum', 'order_value_above_maximum',
  'credit_check_skipped', 'credit_blocked', 'credit_data_missing', 'credit_within_limit', 'credit_over_limit',
] as const

const SIGNAL_CASES: [string, NonNullable<Signal['params']>, string, string][] = [
  ['full_coverage', {}, 'Covers the entire requested quantity', 'Pokrywa całą zamówioną ilość'],
  ['incomplete_coverage', { covered: 50, requested: 80 }, 'Covers 50 of 80 pcs', 'Pokrywa 50 z 80 szt.'],
  ['deadline_met', {}, 'Delivery meets the customer’s deadline', 'Realizacja w terminie klienta'],
  ['no_deadline', {}, 'No deadline in the inquiry', 'Zapytanie bez terminu'],
  ['deadline_missed', { fulfilled_on: '2026-11-09', deadline: '2026-11-06' },
    'Delivery on 9 Nov 2026 is after the deadline of 6 Nov 2026', 'Realizacja 9 lis 2026 po terminie 6 lis 2026'],
  ['compat_full', { product_code: 'ABC-110' }, 'Substitute ABC-110 is fully compatible', 'Zamiennik ABC-110 w pełni zgodny'],
  ['compat_partial', { product_code: 'ABC-120' }, 'Substitute ABC-120 is only partly compatible', 'Zamiennik ABC-120 zgodny tylko częściowo'],
  ['consent_confirmed', {}, 'The customer agreed to a substitute', 'Klient zgodził się na zamiennik'],
  ['consent_unconfirmed', {}, 'Consent to a substitute has not been confirmed', 'Brak potwierdzenia zgody na zamiennik'],
  ['history_accepted', {}, 'The customer has accepted substitutes before', 'Klient przyjmował już zamienniki'],
  ['history_declined', {}, 'The customer has rejected substitutes before', 'Klient odrzucał już zamienniki'],
  ['history_none', {}, 'The customer has not received substitutes before', 'Klient nie dostawał dotąd zamienników'],
  ['history_mixed', {}, 'The customer has both accepted and rejected substitutes', 'Klient raz przyjmował, raz odrzucał zamienniki'],
  ['two_sources', {}, 'The shortage is supplied from two sources: a substitute and a supplier', 'Brak uzupełniany z dwóch źródeł: zamiennik i dostawca'],
]

describe('business message catalogue', () => {
  it('covers every policy producer branch', () => {
    expect(Object.keys(POLICY_REASON_KEYS).sort()).toEqual([...REASON_CODES].sort())
  })

  for (const language of ['en', 'pl'] as const) {
    const resources = language === 'pl' ? pl : en
    it.each(REASON_CODES)(`translates policy %s in ${language} without reading original text`, async (code) => {
      await i18n.changeLanguage(language)
      const rule = { ...RULE, reason_code: code, reason: '<original must not be parsed>' }
      expect(policyReason(rule, i18n.t)).toBe(resources.business.policy[code])
    })

    it.each(SIGNAL_CASES)(`translates signal %s with its own details in ${language}`, async (code, params, english, polish) => {
      await i18n.changeLanguage(language)
      const value = signal(code, params)
      const before = JSON.stringify(value)
      expect(signalMessage(value, i18n.t)).toBe(language === 'pl' ? polish : english)
      expect(JSON.stringify(value)).toBe(before)
    })

    it(`uses only rule and verdict for all historical policies in ${language}`, async () => {
      await i18n.changeLanguage(language)
      for (const code of ['margin', 'discount', 'order_value', 'credit'] as RuleCode[]) {
        for (const verdict of ['pass', 'fail', 'not_evaluated'] as RuleVerdict[]) {
          const old = { ...RULE, code, verdict, actual: null, threshold: null }
          const expected = resources.business.legacyPolicy[code][verdict]
          expect(policyReason(old, i18n.t)).toBe(expected)
          expect(policyReason({ ...old, reason_code: null }, i18n.t)).toBe(expected)
        }
      }
      const oldBlocked = { ...RULE, code: 'credit' as const, reason: 'Customer credit blocked' }
      const oldOverLimit = { ...oldBlocked, reason: 'Balance + selected option value over limit' }
      expect(policyReason(oldBlocked, i18n.t)).toBe(policyReason(oldOverLimit, i18n.t))
    })

    it(`uses safe generic descriptions for missing details in ${language}`, async () => {
      await i18n.changeLanguage(language)
      const cases = [
        ['incomplete_coverage', { covered: 50 }],
        ['incomplete_coverage', { covered: '50', requested: 80 }],
        ['incomplete_coverage', { covered: -1, requested: 80 }],
        ['incomplete_coverage', { covered: 1.5, requested: 80 }],
        ['deadline_missed', { fulfilled_on: '2026-02-30', deadline: '2026-03-01' }],
        ['deadline_missed', { fulfilled_on: '2026-11-09', deadline: 'not a date' }],
        ['deadline_missed', { fulfilled_on: '2026-11-09T00:00:00Z' }],
        ['compat_full', { product_code: '' }],
        ['compat_partial', { product_code: 123 }],
      ] as [string, NonNullable<Signal['params']>][]
      for (const [code, params] of cases) {
        const generic = signalMessage(signal(code), i18n.t)
        expect(signalMessage(signal(code, params), i18n.t)).toBe(generic)
        expect(generic).not.toMatch(/undefined|null|2026|123|original/)
      }
      expect(signalMessage(signal('deadline_missed', { fulfilled_on: '2028-02-29', deadline: '2028-02-28' }), i18n.t))
        .not.toBe(signalMessage(signal('deadline_missed'), i18n.t))
    })

    it(`translates every recognized capability and uncertain field suffix in ${language}`, async () => {
      await i18n.changeLanguage(language)
      const capabilities = {
        'substitute-compatibility': resources.orchestration.capability.substituteCompatibility,
        'substitute-availability': resources.orchestration.capability.substituteAvailability,
        'supplier-availability': resources.orchestration.capability.supplierAvailability,
        'customer-history': resources.orchestration.capability.customerHistory,
      }
      for (const prefix of ['task_failed', 'not_checked', 'alternative_not_checked'] as const) {
        for (const [capability, label] of Object.entries(capabilities)) {
          expect(signalMessage(signal(`${prefix}:${capability}`), i18n.t))
            .toBe(resources.business.signal[prefix].replace('{{capability}}', label))
        }
      }
      for (const field of ['customer', 'product_code', 'quantity'] as const) {
        expect(signalMessage(signal(`uncertain_input:${field}`), i18n.t))
          .toBe(resources.business.signal.uncertain_input.replace('{{field}}', resources.checks.input[field]))
      }
    })

    it(`preserves completely unknown original business text in ${language}`, async () => {
      await i18n.changeLanguage(language)
      for (const code of ['new_code', 'toString', '__proto__', 'task_failed:new-capability',
        'uncertain_input:new-field', 'not_checked:customer-history:extra']) {
        expect(signalMessage(signal(code), i18n.t)).toBe('An original business signal')
        expect(policyReason({ ...RULE, reason_code: code }, i18n.t)).toBe(RULE.reason)
      }
    })
  }

  it('formats quantities in the UI language without guessing missing historical data', async () => {
    const value = signal('incomplete_coverage', { covered: 12345, requested: 54321 })
    await i18n.changeLanguage('en')
    expect(signalMessage(value, i18n.t)).toBe('Covers 12,345 of 54,321 pcs')
    await i18n.changeLanguage('pl')
    expect(signalMessage(value, i18n.t)).toBe(`Pokrywa ${new Intl.NumberFormat('pl-PL').format(12345)} z ${new Intl.NumberFormat('pl-PL').format(54321)} szt.`)
  })
})
