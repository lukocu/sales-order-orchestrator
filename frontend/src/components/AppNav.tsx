import { Link, useLocation } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

// The active link reads as current by weight and background, not colour alone.
const LINK = 'aria-[current=page]:bg-accent aria-[current=page]:font-semibold'

// Header links for signed-in users. The inbox is current on `/` and on every inquiry
// address; the explicit aria-current covers `/inquiries/*`, which the exact `/` link misses.
function AppNav() {
  const { t } = useTranslation()
  const pathname = useLocation({ select: (location) => location.pathname })
  const inboxCurrent = pathname === '/' || pathname.startsWith('/inquiries/')
  const systemCurrent = pathname === '/system'

  return (
    <nav aria-label={t('nav.label')} className="flex flex-wrap items-center gap-1">
      <Button asChild variant="ghost" size="sm" className={LINK}>
        <Link
          to="/"
          activeOptions={{ exact: true }}
          activeProps={{}}
          aria-current={inboxCurrent ? 'page' : undefined}
        >
          {t('nav.inbox')}
        </Link>
      </Button>
      <Button asChild variant="ghost" size="sm" className={LINK}>
        <Link to="/system" activeProps={{}} aria-current={systemCurrent ? 'page' : undefined}>
          {t('nav.system')}
        </Link>
      </Button>
    </nav>
  )
}

export default AppNav
