import type { TFunction } from 'i18next'
import type { LineSource, OptionKind } from '../api/analysis'

type VariantLike = {
  kind: OptionKind
  lines: { source: LineSource; product_code: string; supplier: string | null }[]
}

// A readable name that tells variants apart: where the lines come from (stock, a substitute
// by code, a supplier by name), in line order, e.g. "Stan + zamiennik ABC-110".
export function variantName(variant: VariantLike, t: TFunction): string {
  const parts = variant.lines.map((line) => {
    switch (line.source) {
      case 'stock':
        return t('variant.stock')
      case 'substitute_stock':
        return t('variant.substitute', { code: line.product_code })
      case 'supplier':
        return t('variant.supplier', { supplier: line.supplier ?? '' })
    }
  })
  if (parts.length === 0) return t(`optionKind.${variant.kind}`)
  if (variant.lines.every((line) => line.source === 'stock')) return t('variant.stockOnly')
  const name = parts.join(' + ')
  return name.charAt(0).toUpperCase() + name.slice(1)
}
