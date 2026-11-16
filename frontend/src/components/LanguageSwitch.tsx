import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { LANGUAGES, type Language } from '@/i18n'

const OPTION_LABEL: Record<Language, string> = { pl: 'PL', en: 'EN' }

function LanguageSwitch() {
  const { t, i18n } = useTranslation()
  const active = i18n.resolvedLanguage ?? i18n.language

  return (
    <div role="group" aria-label={t('language.label')} className="flex items-center gap-1">
      {LANGUAGES.map((language) => {
        const pressed = active === language
        return (
          <Button
            key={language}
            type="button"
            size="sm"
            variant={pressed ? 'outline' : 'ghost'}
            aria-pressed={pressed}
            aria-label={`${OPTION_LABEL[language]} – ${t(`language.${language}`)}`}
            onClick={() => void i18n.changeLanguage(language)}
          >
            <span lang={language}>{OPTION_LABEL[language]}</span>
          </Button>
        )
      })}
    </div>
  )
}

export default LanguageSwitch
