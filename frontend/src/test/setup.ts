import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import i18n, { STORAGE_KEY } from '../i18n'

// jsdom has no scrolling; the router resets the scroll position after each navigation.
window.scrollTo = () => {}

// Tests run in English so queries match the English strings.
beforeEach(async () => {
  await i18n.changeLanguage('en')
  localStorage.removeItem(STORAGE_KEY)
})

// Vitest globals are off, so Testing Library cannot register its own cleanup.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
