import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchMe, logout, UnauthorizedError, type User } from './api/auth'
import AppShell from './components/AppShell'
import HealthFooter from './components/HealthFooter'
import Inbox from './components/Inbox'
import LoginForm from './components/LoginForm'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'authenticated'; user: User }
  // `message` is null when the failure carried no text.
  | { kind: 'error'; message: string | null }

function App() {
  const { t } = useTranslation()
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [signingOut, setSigningOut] = useState(false)
  // Server text, or null for the translated fallback (translated at render time).
  const [signOutError, setSignOutError] = useState<{ message: string | null } | null>(null)

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
            : { kind: 'error', message: error instanceof Error ? error.message : null },
        )
      },
    )
    return () => controller.abort()
  }, [attempt])

  const handleSignedIn = useCallback((user: User) => {
    setState({ kind: 'authenticated', user })
  }, [])
  // After Sign out and whenever the API answers 401 (session gone).
  const handleSignedOut = useCallback(() => {
    setSigningOut(false)
    setSignOutError(null)
    setState({ kind: 'anonymous' })
  }, [])

  async function handleSignOut() {
    setSigningOut(true)
    setSignOutError(null)
    try {
      await logout()
    } catch (error) {
      // A 401 means the session is already gone, which is what Sign out wants.
      if (!(error instanceof UnauthorizedError)) {
        setSignOutError({ message: error instanceof Error ? error.message : null })
        setSigningOut(false)
        return
      }
    }
    handleSignedOut()
  }

  function retry() {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }

  return (
    <AppShell
      user={state.kind === 'authenticated' ? state.user : null}
      onSignOut={handleSignOut}
      signingOut={signingOut}
    >
      {state.kind === 'loading' && <p className="text-muted-foreground">{t('app.loading')}</p>}
      {state.kind === 'error' && (
        <Card role="alert" className="gap-0 rounded-lg py-5 shadow-none">
          <CardContent className="grid justify-items-start gap-3">
            <p className="text-destructive">
              {t('app.sessionError', { message: state.message ?? t('app.unknownError') })}
            </p>
            <Button type="button" variant="outline" onClick={retry}>
              {t('app.retry')}
            </Button>
          </CardContent>
        </Card>
      )}
      {state.kind === 'anonymous' && <LoginForm onSignedIn={handleSignedIn} />}
      {state.kind === 'authenticated' && signOutError && (
        <p className="text-destructive" role="alert">
          {signOutError.message ?? t('inbox.genericError')}
        </p>
      )}
      {state.kind === 'authenticated' && (
        <Inbox user={state.user} onUnauthorized={handleSignedOut} />
      )}
      {state.kind === 'authenticated' && <HealthFooter />}
    </AppShell>
  )
}

export default App
