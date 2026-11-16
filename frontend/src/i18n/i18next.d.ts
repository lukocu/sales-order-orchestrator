import 'i18next'
import type en from './locales/en.json'

// Type-checks t('…') keys against the English resources.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: { translation: typeof en }
  }
}
