import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchHealth, type HealthResult } from '../api/health'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

type State = { kind: 'loading' } | HealthResult

// The status reads as a word in the badge; the tone only reinforces it.
const BADGE = {
  loading: 'outline',
  ok: 'success',
  degraded: 'warning',
  error: 'destructive',
} as const satisfies Record<State['kind'], string>

// `/system`: API, database and migration status from the public /api/health.
function SystemPage() {
  const { t } = useTranslation()
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  // Once per mount and per Refresh; a newer request aborts the older one.
  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal).then(setState, () => {
      // Only an aborted request rejects; a newer one (or nothing) owns the state.
    })
    return () => controller.abort()
  }, [attempt])

  function refresh() {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }

  return (
    <section aria-labelledby="system-heading" className="grid gap-4">
      <h2 id="system-heading" className="text-lg font-semibold">
        {t('system.title')}
      </h2>
      <Card className="gap-0 rounded-lg py-5 shadow-none">
        <CardContent className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-1">
              <h3 className="text-sm font-semibold text-muted-foreground">{t('health.heading')}</h3>
              <div role="status" className="grid justify-items-start gap-1">
                <Badge variant={BADGE[state.kind]} className="text-sm">
                  {t(`health.${state.kind}`)}
                </Badge>
                {state.kind === 'error' && (
                  <p className="text-sm text-muted-foreground">{state.message}</p>
                )}
              </div>
            </div>
            <Button type="button" variant="outline" onClick={refresh}>
              {t('health.refresh')}
            </Button>
          </div>
          {(state.kind === 'ok' || state.kind === 'degraded') && (
            <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
              <dt className="text-muted-foreground">{t('health.api')}</dt>
              <dd className="font-mono">{t('health.apiOk')}</dd>
              <dt className="text-muted-foreground">{t('health.database')}</dt>
              <dd className="font-mono">{state.health.database}</dd>
              <dt className="text-muted-foreground">{t('health.migration')}</dt>
              <dd className="font-mono break-all">
                {state.health.migration ?? t('health.unknown')}
              </dd>
            </dl>
          )}
        </CardContent>
      </Card>
    </section>
  )
}

export default SystemPage
