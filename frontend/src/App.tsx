import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResult } from './api/health'

type State = { kind: 'loading' } | HealthResult

const STATUS_LABEL: Record<State['kind'], string> = {
  loading: 'Checking…',
  ok: 'All systems operational',
  degraded: 'Degraded',
  error: 'Unavailable',
}

function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal).then(setState, () => {
      // Only an aborted request rejects; the component is gone, nothing to update.
    })
    return () => controller.abort()
  }, [])

  return (
    <main className="page">
      <h1>Sales Order Orchestrator</h1>
      <section className={`status status--${state.kind}`} aria-live="polite">
        <h2>System status</h2>
        <p className="status__summary">{STATUS_LABEL[state.kind]}</p>
        {state.kind === 'error' && <p className="status__detail">{state.message}</p>}
        {(state.kind === 'ok' || state.kind === 'degraded') && (
          <dl className="status__list">
            <dt>API</dt>
            <dd>ok</dd>
            <dt>Database</dt>
            <dd>{state.health.database}</dd>
            <dt>Migration</dt>
            <dd>{state.health.migration ?? 'unknown'}</dd>
          </dl>
        )}
      </section>
    </main>
  )
}

export default App
