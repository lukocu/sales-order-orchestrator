import { Link, useLocation } from '@tanstack/react-router'
import { Activity, Inbox, ListChecks } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useSession } from '../session'
import { useSupervisorQueue } from '../useSupervisorQueue'

// The active link reads as current by weight and background, not colour alone.
const LINK =
  'shrink-0 justify-start gap-2 text-muted-foreground hover:text-foreground md:w-full aria-[current=page]:bg-accent aria-[current=page]:font-semibold aria-[current=page]:text-foreground'

type Section = 'inbox' | 'approvals' | 'system'

// null on an address that belongs to no section (the not-found page).
function sectionOf(pathname: string): Section | null {
  if (pathname === '/' || pathname.startsWith('/inquiries/')) return 'inbox'
  if (pathname.startsWith('/approvals')) return 'approvals'
  if (pathname === '/system') return 'system'
  return null
}

const SECTION_LABEL = {
  inbox: 'nav.inbox',
  approvals: 'supervisor.nav.queue',
  system: 'nav.system',
} as const

// The top bar's "where am I": the section the current address belongs to.
export function SectionCrumb() {
  const { t } = useTranslation()
  const pathname = useLocation({ select: (location) => location.pathname })
  const section = sectionOf(pathname)
  return section === null ? null : <span className="font-medium">{t(SECTION_LABEL[section])}</span>
}

// Sidebar links for signed-in users (a row on narrow screens, a column from md up). The inbox
// is current on `/` and on every inquiry address; the explicit aria-current covers
// `/inquiries/*`, which the exact `/` link misses.
function AppNav() {
  const { t } = useTranslation()
  const { user } = useSession()
  const queue = useSupervisorQueue()
  const pathname = useLocation({ select: (location) => location.pathname })
  const section = sectionOf(pathname)
  const queueData = queue.state.kind === 'ready'
    ? queue.state.queue
    : queue.state.kind === 'error'
      ? queue.state.previous
      : null

  return (
    <nav aria-label={t('nav.label')} className="flex flex-wrap gap-1 md:flex-col md:flex-nowrap">
      <Button asChild variant="ghost" size="sm" className={LINK}>
        <Link
          to="/"
          activeOptions={{ exact: true }}
          activeProps={{}}
          aria-current={section === 'inbox' ? 'page' : undefined}
        >
          <Inbox aria-hidden="true" />
          {t('nav.inbox')}
        </Link>
      </Button>
      {user.role === 'supervisor' && (
        <Button asChild variant="ghost" size="sm" className={LINK}>
          <Link to="/approvals" activeProps={{}} aria-current={section === 'approvals' ? 'page' : undefined}>
            <ListChecks aria-hidden="true" />
            {t('supervisor.nav.queue')}
            {queueData !== null && (
              <span className="ms-auto rounded-full border px-1.5 font-mono text-xs tabular-nums">
                {queueData.total}
              </span>
            )}
            {queue.state.kind === 'error' && <span className="sr-only">{t('supervisor.queue.stale')}</span>}
          </Link>
        </Button>
      )}
      <Button asChild variant="ghost" size="sm" className={LINK}>
        <Link to="/system" activeProps={{}} aria-current={section === 'system' ? 'page' : undefined}>
          <Activity aria-hidden="true" />
          {t('nav.system')}
        </Link>
      </Button>
    </nav>
  )
}

export default AppNav
