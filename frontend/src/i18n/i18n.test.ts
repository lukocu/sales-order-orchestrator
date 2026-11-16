import { describe, expect, it } from 'vitest'
import en from './locales/en.json'
import pl from './locales/pl.json'

function flatten(value: unknown, prefix = ''): Array<[string, unknown]> {
  if (typeof value !== 'object' || value === null) return [[prefix, value]]
  return Object.entries(value).flatMap(([key, child]) =>
    flatten(child, prefix ? `${prefix}.${key}` : key),
  )
}

describe('locale resources', () => {
  const plEntries = flatten(pl)
  const enEntries = flatten(en)

  it('have the same keys in Polish and English', () => {
    const keys = (entries: Array<[string, unknown]>) => entries.map(([key]) => key).sort()
    expect(keys(plEntries)).toEqual(keys(enEntries))
  })

  it.each([
    ['pl', plEntries],
    ['en', enEntries],
  ])('has no empty values in %s', (_, entries) => {
    for (const [key, value] of entries) {
      expect(typeof value, key).toBe('string')
      expect((value as string).trim(), key).not.toBe('')
    }
  })
})
