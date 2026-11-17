import { useCallback, useEffect, useMemo, useState } from 'react'
import { Outlet } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { fetchMe, logout, UnauthorizedError, type User } from './api/auth'
import AppNav from './components/AppNav'
import AppShell from './components/AppShell'
import LoginForm from './components/LoginForm'
import { SessionContext, type Session } from './session'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'authenticated'; user: User }
  // `message` is null when the failure carried no text.
  | { kind: 'error'; message: string | null }

// The root route's component: it stays mounted across navigation, so the session lives here.
// Without a session every address renders sign-in in place, and the URL is kept.
function App() {
  const { t } = useTranslation()
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [signingOut, setSigningOut] = useState(false)
  // True once the app went authenticated -> anonymous: the sign-in heading takes focus then,
  // not on the first load.
  const [focusLogin, setFocusLogin] = useState(false)
  // Server text, or null for the translated fallback (translated at render time).
  const [signOutError, setSignOutError] = useState<{ message: string | null } | null>(null)

  // Once per mount (and per Retry): the session (GET /api/auth/me) picks the view.
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
    setFocusLogin(false)
    setState({ kind: 'authenticated', user })
  }, [])
  // After Sign out and whenever the API answers 401 (session gone).
  const handleSignedOut = useCallback(() => {
    setFocusLogin(true)
    setSigningOut(false)
    setSignOutError(null)
    setState({ kind: 'anonymous' })
  }, [])

  async function handleSignOut() {
    if (signingOut) return
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

  const user = state.kind === 'authenticated' ? state.user : null
  const session = useMemo<Session | null>(
    () => (user === null ? null : { user, onUnauthorized: handleSignedOut }),
    [user, handleSignedOut],
  )

  function retry() {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }

  return (
    <AppShell
      user={user}
      onSignOut={handleSignOut}
      signingOut={signingOut}
      nav={user !== null ? <AppNav /> : undefined}
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
      {state.kind === 'anonymous' && <LoginForm onSignedIn={handleSignedIn} focusHeading={focusLogin} />}
      {state.kind === 'authenticated' && signOutError && (
        <p className="text-destructive" role="alert">
          {signOutError.message ?? t('inbox.genericError')}
        </p>
      )}
      {session !== null && (
        <SessionContext.Provider value={session}>
          <Outlet />
        </SessionContext.Provider>
      )}
    </AppShell>
  )
}

export default App
