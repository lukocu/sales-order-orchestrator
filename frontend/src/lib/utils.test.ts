import { describe, expect, it } from 'vitest'
import { cn } from '@/lib/utils'

describe('cn', () => {
  it('lets the last conflicting Tailwind utility win', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })

  it('drops falsy values and keeps the rest in order', () => {
    expect(cn('a', false, null, undefined, 0, '', 'b', { c: true, d: false })).toBe('a b c')
  })
})
