import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import type { LineSource, OptionKind } from '../api/analysis'
import { variantName } from './variantName'

const t = i18n.t.bind(i18n)

function variant(kind: OptionKind, lines: [LineSource, string, string?][]) {
  return {
    kind,
    lines: lines.map(([source, product_code, supplier]) => ({
      source,
      product_code,
      supplier: supplier ?? null,
    })),
  }
}

describe('variantName', () => {
  it('names a stock-only variant as a partial delivery', () => {
    expect(variantName(variant('partial_delivery', [['stock', 'ABC-100']]), t)).toBe(
      'Stock only (partial delivery)',
    )
  })

  it('names stock plus a substitute by its code', () => {
    const v = variant('substitute', [
      ['stock', 'ABC-100'],
      ['substitute_stock', 'ABC-110'],
    ])
    expect(variantName(v, t)).toBe('Stock + substitute ABC-110')
  })

  it('names stock plus a supplier by its name', () => {
    const v = variant('other_source', [
      ['stock', 'ABC-100'],
      ['supplier', 'ABC-100', 'Hydro-Valve'],
    ])
    expect(variantName(v, t)).toBe('Stock + supplier Hydro-Valve')
  })

  it('names a combined variant with every part', () => {
    const v = variant('combined', [
      ['stock', 'ABC-100'],
      ['substitute_stock', 'ABC-110'],
      ['supplier', 'ABC-110', 'Hydro-Valve'],
    ])
    expect(variantName(v, t)).toBe('Stock + substitute ABC-110 + supplier Hydro-Valve')
  })

  it('capitalises a variant without own stock', () => {
    expect(variantName(variant('substitute', [['substitute_stock', 'ABC-110']]), t)).toBe(
      'Substitute ABC-110',
    )
  })

  it('falls back to the option kind when there are no lines', () => {
    expect(variantName(variant('combined', []), t)).toBe('Stock + substitute + supplier')
  })
})
