import { describe, expect, it } from 'vitest'
import i18n from '@/i18n'
import { formatDate } from './format'

// Noon UTC keeps the day the same in any test time zone.
const ISO = '2026-11-14T12:00:00Z'

describe('formatDate', () => {
  it('uses the English month name when the UI is in English', () => {
    expect(formatDate(ISO)).toMatch(/^14 Nov 2026/)
  })

  it('switches to the Polish month name with the UI language', async () => {
    await i18n.changeLanguage('pl')
    expect(formatDate(ISO)).toMatch(/^14 lis 2026/)
  })

  it('returns the input when it is not a date', () => {
    expect(formatDate('not a date')).toBe('not a date')
  })
})
