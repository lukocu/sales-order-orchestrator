import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { resolveInitialLanguage, STORAGE_KEY } from '../i18n'
import LanguageSwitch from './LanguageSwitch'

function storageWith(value: string | null): Pick<Storage, 'getItem'> {
  return { getItem: (key) => (key === STORAGE_KEY ? value : null) }
}

describe('LanguageSwitch', () => {
  it('switches to Polish in place and persists the choice', async () => {
    render(<LanguageSwitch />)

    const group = screen.getByRole('group', { name: 'Language' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'EN – English' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'PL – Polski' })).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(screen.getByRole('button', { name: 'PL – Polski' }))

    expect(await screen.findByRole('group', { name: 'Język' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PL – Polski' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'EN – English' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('PL')).toHaveAttribute('lang', 'pl')
    expect(document.documentElement.lang).toBe('pl')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('pl')
  })

  it('falls back to Polish when the stored language is invalid', () => {
    expect(resolveInitialLanguage(storageWith('de'))).toBe('pl')
    expect(resolveInitialLanguage(storageWith(null))).toBe('pl')
    expect(resolveInitialLanguage(undefined)).toBe('pl')
    expect(resolveInitialLanguage(storageWith('en'))).toBe('en')
  })
})
