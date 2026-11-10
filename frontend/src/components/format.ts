import type { RunSummary, StepSummary } from '../api/analysis'

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : DATE_FORMAT.format(date)
}

// Decimal strings from the API (may be in exponent form, e.g. "1E-7").
export function formatUsd(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `$${value}`
  const [whole, fraction = ''] = amount.toFixed(10).split('.')
  return `$${whole}.${fraction.replace(/0+$/, '').padEnd(2, '0')}`
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
