import { useSyncExternalStore } from 'react'

// The user's choice; "system" follows the OS (prefers-color-scheme) and is the default.
export type ThemeChoice = 'light' | 'dark' | 'system'
export type Theme = 'light' | 'dark'

export const THEME_CHOICES: readonly ThemeChoice[] = ['light', 'dark', 'system']
// Also read by the inline script in index.html and kitchen-sink.html, which sets the theme
// before the first paint; keep the key and the values in step with it.
export const THEME_STORAGE_KEY = 'theme'

const DARK_QUERY = '(prefers-color-scheme: dark)'

function isChoice(value: unknown): value is ThemeChoice {
  return value === 'light' || value === 'dark' || value === 'system'
}

// Storage can be missing or throw (private mode, blocked site data): fall back to "system".
export function readThemeChoice(storage: Pick<Storage, 'getItem'> | undefined = globalThis.localStorage): ThemeChoice {
  try {
    const stored = storage?.getItem(THEME_STORAGE_KEY)
    return isChoice(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

function systemTheme(): Theme {
  return typeof window.matchMedia === 'function' && window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
}

export function resolveTheme(choice: ThemeChoice): Theme {
  return choice === 'system' ? systemTheme() : choice
}

let current: ThemeChoice = readThemeChoice()
const listeners = new Set<() => void>()

function apply() {
  document.documentElement.dataset.theme = resolveTheme(current)
}

export function setThemeChoice(choice: ThemeChoice) {
  current = choice
  try {
    if (choice === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
    else localStorage.setItem(THEME_STORAGE_KEY, choice)
  } catch {
    // Not remembered, but still applied for this visit.
  }
  apply()
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// The current choice, shared by every switch on the page.
export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(subscribe, () => current)
}

// On "system", follow the OS when it switches between light and dark.
if (typeof window.matchMedia === 'function') {
  window.matchMedia(DARK_QUERY).addEventListener('change', () => {
    if (current === 'system') apply()
  })
}
apply()
