import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { setThemeChoice, THEME_CHOICES, useThemeChoice, type ThemeChoice } from '../theme'

const ICON: Record<ThemeChoice, LucideIcon> = { light: Sun, dark: Moon, system: Monitor }

// A pill of three icon buttons: light, dark and the OS setting. The pressed one is filled and
// ringed in the input colour (3:1 against the card, so the state does not rest on a faint fill);
// each button is named by its label (and shows it on hover), not by the icon alone.
function ThemeSwitch() {
  const { t } = useTranslation()
  const choice = useThemeChoice()

  return (
    <div role="group" aria-label={t('theme.label')} className="flex items-center gap-0.5 rounded-full border p-0.5">
      {THEME_CHOICES.map((option) => {
        const Icon = ICON[option]
        const pressed = choice === option
        return (
          <Button
            key={option}
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-pressed={pressed}
            aria-label={t(`theme.${option}`)}
            title={t(`theme.${option}`)}
            onClick={() => setThemeChoice(option)}
            className="rounded-full text-muted-foreground hover:text-foreground aria-pressed:bg-background aria-pressed:text-foreground aria-pressed:ring-1 aria-pressed:ring-input"
          >
            <Icon aria-hidden="true" className="size-3.5" />
          </Button>
        )
      })}
    </div>
  )
}

export default ThemeSwitch
