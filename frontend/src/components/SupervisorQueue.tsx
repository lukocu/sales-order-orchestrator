import { useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { useSupervisorQueue } from '../useSupervisorQueue'
import { RULE_LABEL } from './policyLabels'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { errorMessage, formatDate } from './format'

function waitAge(date: string, t: ReturnType<typeof useTranslation>['t']): string {
  const elapsed = Math.max(0, Date.now() - Date.parse(date))
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 60) return t('supervisor.age.minutes', { count: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('supervisor.age.hours', { count: hours })
  return t('supervisor.age.days', { count: Math.floor(hours / 24) })
}

function SupervisorQueue() {
  const { t } = useTranslation()
  const { state, refresh } = useSupervisorQueue()

  useEffect(() => {
    void refresh()
  }, [refresh])

  const queue = state.kind === 'ready' ? state.queue : state.kind === 'error' ? state.previous : null

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby="supervisor-queue-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="supervisor-queue-heading" className="text-xl font-semibold">
            {t('supervisor.queue.heading')}
          </h2>
          {queue !== null && (
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {t('supervisor.queue.count', { count: queue.total })}
              {state.kind === 'error' && ` · ${t('supervisor.queue.stale')}`}
            </p>
          )}
        </div>
        <Button type="button" variant="outline" onClick={() => void refresh(true)}>
          {t('supervisor.queue.refresh')}
        </Button>
      </div>

      {state.kind === 'loading' && <p role="status">{t('supervisor.queue.loading')}</p>}
      {state.kind === 'error' && (
        <Card role="alert" className="gap-0 rounded-lg py-4 shadow-none">
          <CardContent className="grid justify-items-start gap-3">
            <p className="text-destructive">{errorMessage(state.error, t)}</p>
            <Button type="button" variant="outline" onClick={() => void refresh(true)}>
              {t('common.retry')}
            </Button>
          </CardContent>
        </Card>
      )}
      {state.kind === 'ready' && state.queue.items.length === 0 && (
        <Card className="rounded-lg shadow-none">
          <CardContent>
            <p className="text-muted-foreground">{t('supervisor.queue.empty')}</p>
          </CardContent>
        </Card>
      )}
      {queue !== null && queue.items.length > 0 && (
        <ul className="grid gap-3">
          {queue.items.map((item) => (
            <li key={item.id}>
              <Link
                to="/approvals/$inquiryId"
                params={{ inquiryId: String(item.id) }}
                className="grid gap-2 rounded-lg border bg-card p-4 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                <span className="flex flex-wrap items-start justify-between gap-2">
                  <span className="font-semibold wrap-anywhere">{item.customer ?? item.sender_name}</span>
                  <span className="text-sm text-muted-foreground">
                    {t('supervisor.queue.waiting', { age: waitAge(item.submitted_at, t) })}
                  </span>
                </span>
                <span className="wrap-anywhere">{item.subject}</span>
                <span className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                  <time dateTime={item.submitted_at}>{formatDate(item.submitted_at)}</time>
                  {item.attention_rules.length > 0 && (
                    <span>{item.attention_rules.map((rule) => t(RULE_LABEL[rule.code])).join(', ')}</span>
                  )}
                  {item.review_state !== 'actionable' && (
                    <span>{t(`supervisor.state.${item.review_state}`)}</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default SupervisorQueue
