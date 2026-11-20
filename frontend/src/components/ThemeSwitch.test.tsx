import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { readThemeChoice, resolveTheme, setThemeChoice, THEME_STORAGE_KEY } from '../theme'
import ThemeSwitch from './ThemeSwitch'

function storageWith(value: string | null): Pick<Storage, 'getItem'> {
  return { getItem: (key) => (key === THEME_STORAGE_KEY ? value : null) }
}

function theme(): string | undefined {
  return document.documentElement.dataset.theme
}

afterEach(() => setThemeChoice('system'))

describe('ThemeSwitch', () => {
  it('follows the system by default and applies and remembers a chosen theme', () => {
    render(<ThemeSwitch />)

    expect(screen.getByRole('group', { name: 'Theme' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'System' })).toHaveAttribute('aria-pressed', 'true')
    expect(theme()).toBe('light')

    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'System' })).toHaveAttribute('aria-pressed', 'false')
    expect(theme()).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    fireEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(theme()).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')

    fireEvent.click(screen.getByRole('button', { name: 'System' }))
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })

  it('keeps every switch on the page in step', () => {
    render(
      <>
        <ThemeSwitch />
        <ThemeSwitch />
      </>,
    )

    fireEvent.click(screen.getAllByRole('button', { name: 'Dark' })[0])

    for (const button of screen.getAllByRole('button', { name: 'Dark' })) {
      expect(button).toHaveAttribute('aria-pressed', 'true')
    }
  })

  it('resolves "system" from the OS preference', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query === '(prefers-color-scheme: dark)' }))
    expect(resolveTheme('system')).toBe('dark')
    expect(resolveTheme('light')).toBe('light')
  })

  it('falls back to "system" when the stored choice is invalid or storage fails', () => {
    expect(readThemeChoice(storageWith('dark'))).toBe('dark')
    expect(readThemeChoice(storageWith('sepia'))).toBe('system')
    expect(readThemeChoice(storageWith(null))).toBe('system')
    expect(readThemeChoice(undefined)).toBe('system')
    expect(
      readThemeChoice({
        getItem: () => {
          throw new Error('blocked')
        },
      }),
    ).toBe('system')
  })
})
