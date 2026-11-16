import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import pl from './locales/pl.json'

export type Language = 'pl' | 'en'

export const LANGUAGES: readonly Language[] = ['pl', 'en']

export const STORAGE_KEY = 'lang'

const DEFAULT_LANGUAGE: Language = 'pl'

function isLanguage(value: unknown): value is Language {
  return value === 'pl' || value === 'en'
}

// localStorage → 'pl'. Storage can be missing or throw (private mode, blocked site data).
export function resolveInitialLanguage(storage: Pick<Storage, 'getItem'> | undefined): Language {
  try {
    const stored = storage?.getItem(STORAGE_KEY)
    return isLanguage(stored) ? stored : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

function browserStorage(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage
  } catch {
    return undefined
  }
}

function applyLanguage(language: string) {
  if (typeof document !== 'undefined') document.documentElement.lang = language
  try {
    browserStorage()?.setItem(STORAGE_KEY, language)
  } catch {
    // Persisting is a convenience; the switch still works for this page.
  }
}

i18n.on('languageChanged', applyLanguage)

// Bundled resources and initAsync: false, so the first render already has the strings.
void i18n.use(initReactI18next).init({
  resources: { pl: { translation: pl }, en: { translation: en } },
  lng: resolveInitialLanguage(browserStorage()),
  fallbackLng: 'en',
  supportedLngs: [...LANGUAGES],
  ns: ['translation'],
  defaultNS: 'translation',
  initAsync: false,
  interpolation: { escapeValue: false },
})

export default i18n
