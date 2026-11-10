import { useCallback, useEffect, useState } from 'react'
import { fetchMe, UnauthorizedError, type User } from './api/auth'
import HealthFooter from './components/HealthFooter'
import Inbox from './components/Inbox'
import LoginForm from './components/LoginForm'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'authenticated'; user: User }
  | { kind: 'error'; message: string }

function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  // No router: the session (GET /api/auth/me) picks the view.
  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal).then(
      (user) => setState({ kind: 'authenticated', user }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        setState(
          error instanceof UnauthorizedError
            ? { kind: 'anonymous' }
            : { kind: 'error', message: error instanceof Error ? error.message : 'Unknown error' },
        )
      },
    )
    return () => controller.abort()
  }, [attempt])

  const handleSignedIn = useCallback((user: User) => {
    setState({ kind: 'authenticated', user })
  }, [])
  const handleSignedOut = useCallback(() => setState({ kind: 'anonymous' }), [])

  function retry() {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }

  return (
    <main className={state.kind === 'authenticated' ? 'page page--wide' : 'page'}>
      <h1>Sales Order Orchestrator</h1>
      {state.kind === 'loading' && <p className="muted">Loading…</p>}
      {state.kind === 'error' && (
        <section className="card" role="alert">
          <p className="error">Could not check your session: {state.message}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </section>
      )}
      {state.kind === 'anonymous' && <LoginForm onSignedIn={handleSignedIn} />}
      {state.kind === 'authenticated' && (
        <Inbox user={state.user} onSignedOut={handleSignedOut} />
      )}
      <HealthFooter />
    </main>
  )
}

export default App
