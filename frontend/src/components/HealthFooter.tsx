import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchHealth, type HealthResult } from '../api/health'

type State = { kind: 'loading' } | HealthResult

function HealthFooter() {
  const { t } = useTranslation()
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal).then(setState, () => {
      // Only an aborted request rejects; the component is gone, nothing to update.
    })
    return () => controller.abort()
  }, [])

  return (
    <footer className={`status status--${state.kind}`} aria-live="polite">
      <h2>{t('health.heading')}</h2>
      <p className="status__summary">{t(`health.${state.kind}`)}</p>
      {state.kind === 'error' && <p className="status__detail">{state.message}</p>}
      {(state.kind === 'ok' || state.kind === 'degraded') && (
        <dl className="status__list">
          <dt>{t('health.api')}</dt>
          <dd>{t('health.apiOk')}</dd>
          <dt>{t('health.database')}</dt>
          <dd>{state.health.database}</dd>
          <dt>{t('health.migration')}</dt>
          <dd>{state.health.migration ?? t('health.unknown')}</dd>
        </dl>
      )}
    </footer>
  )
}

export default HealthFooter
