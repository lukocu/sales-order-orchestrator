import { Link, useLocation } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useSession } from '../session'
import { useSupervisorQueue } from '../useSupervisorQueue'

// The active link reads as current by weight and background, not colour alone.
const LINK = 'aria-[current=page]:bg-accent aria-[current=page]:font-semibold'

// Header links for signed-in users. The inbox is current on `/` and on every inquiry
// address; the explicit aria-current covers `/inquiries/*`, which the exact `/` link misses.
function AppNav() {
  const { t } = useTranslation()
  const { user } = useSession()
  const queue = useSupervisorQueue()
  const pathname = useLocation({ select: (location) => location.pathname })
  const inboxCurrent = pathname === '/' || pathname.startsWith('/inquiries/')
  const systemCurrent = pathname === '/system'
  const approvalsCurrent = pathname.startsWith('/approvals')
  const queueData = queue.state.kind === 'ready'
    ? queue.state.queue
    : queue.state.kind === 'error'
      ? queue.state.previous
      : null

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
      {user.role === 'supervisor' && (
        <Button asChild variant="ghost" size="sm" className={LINK}>
          <Link to="/approvals" activeProps={{}} aria-current={approvalsCurrent ? 'page' : undefined}>
            {t('supervisor.nav.queue')}
            {queueData !== null && <span className="ms-2 rounded-full border px-1.5 text-xs tabular-nums">{queueData.total}</span>}
            {queue.state.kind === 'error' && <span className="sr-only">{t('supervisor.queue.stale')}</span>}
          </Link>
        </Button>
      )}
      <Button asChild variant="ghost" size="sm" className={LINK}>
        <Link to="/system" activeProps={{}} aria-current={systemCurrent ? 'page' : undefined}>
          {t('nav.system')}
        </Link>
      </Button>
    </nav>
  )
}

export default AppNav
