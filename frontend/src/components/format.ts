import type { RunSummary, StepSummary } from '../api/analysis'
import i18n, { type Language } from '@/i18n'

// Dates follow the UI language; resolved at call time, so a re-render after a switch
// picks up the new format.
const DATE_LOCALE: Record<Language, string> = { pl: 'pl-PL', en: 'en-GB' }
const dateFormats = new Map<string, Intl.DateTimeFormat>()

function dateFormat(): Intl.DateTimeFormat {
  const language = i18n.resolvedLanguage === 'pl' ? 'pl' : 'en'
  const locale = DATE_LOCALE[language]
  let format = dateFormats.get(locale)
  if (format === undefined) {
    format = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' })
    dateFormats.set(locale, format)
  }
  return format
}

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : dateFormat().format(date)
}

// Decimal strings from the API (may be in exponent form, e.g. "1E-7").
export function formatUsd(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `$${value}`
  const [whole, fraction = ''] = amount.toFixed(10).split('.')
  return `$${whole}.${fraction.replace(/0+$/, '').padEnd(2, '0')}`
}

// Decimal strings from the API, e.g. "5.00" → "5%", "10.50" → "10.5%".
export function formatPercent(value: string): string {
  const trimmed = value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value
  return `${trimmed}%`
}

export function formatPln(value: string | null): string {
  return value === null ? '—' : `${value} PLN`
}

export function formatMs(ms: number): string {
  return `${ms < 10 ? ms.toFixed(1) : Math.round(ms)} ms`
}

export function stepCost(step: StepSummary): string {
  if (step.price_status === 'not_applicable') return '—'
  if (step.price_status === 'unpriced' || step.cost_usd === null) return 'not priced'
  return `${formatUsd(step.cost_usd)} list price`
}

export function totalCost(run: RunSummary): string {
  const anyPriced = run.steps.some((step) => step.price_status === 'priced')
  if (!anyPriced) return run.totals.cost_complete ? '—' : 'not priced'
  const cost = `${formatUsd(run.totals.cost_usd)} list price`
  return run.totals.cost_complete ? cost : `${cost} (some steps not priced)`
}

export function totalDuration(run: RunSummary): string {
  return formatMs(run.totals.duration_ms ?? run.totals.steps_duration_ms)
}
