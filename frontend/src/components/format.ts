import type { TFunction } from 'i18next'
import type { LineSource } from '../api/analysis'
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
    format = new Intl.DateTimeFormat(locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
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

// The text of an error shown in a section; an error without a message reads as a generic one.
export function errorMessage(error: unknown, t: TFunction): string {
  return error instanceof Error ? error.message : t('common.genericError')
}

export function deadlineText(meets: boolean | null, t: TFunction): string {
  if (meets === null) return t('common.deadline.none')
  return meets ? t('common.deadline.meets') : t('common.deadline.misses')
}

export function sourceText(
  line: { source: LineSource; supplier: string | null },
  t: TFunction,
): string {
  switch (line.source) {
    case 'stock':
      return t('common.source.stock')
    case 'substitute_stock':
      return t('common.source.substituteStock')
    case 'supplier':
      return t('common.source.supplier', { name: line.supplier ?? '—' })
  }
}
