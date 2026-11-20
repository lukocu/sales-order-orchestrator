import { useCallback, useEffect, useMemo, useState } from 'react'
import { Outlet } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { fetchMe, logout, UnauthorizedError, type User } from './api/auth'
import { describeError, type ErrorDescriptor } from './api/errorMessages'
import { errorMessage } from './components/format'
import AppNav, { SectionCrumb } from './components/AppNav'
import AppShell from './components/AppShell'
import LoginForm from './components/LoginForm'
import { SessionContext, type Session } from './session'
import { SupervisorQueueProvider } from './supervisorQueue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'authenticated'; user: User }
  | { kind: 'error'; error: ErrorDescriptor }

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
  const [signOutError, setSignOutError] = useState<ErrorDescriptor | null>(null)
  const [expiredError, setExpiredError] = useState<ErrorDescriptor | null>(null)

  // Once per mount (and per Retry): the session (GET /api/auth/me) picks the view.
  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal).then(
      (user) => setState({ kind: 'authenticated', user }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) setState({ kind: 'anonymous' })
        else {
          const descriptor = describeError(error)
          if (descriptor !== null) setState({ kind: 'error', error: descriptor })
        }
      },
    )
    return () => controller.abort()
  }, [attempt])

  const handleSignedIn = useCallback((user: User) => {
    setFocusLogin(false)
    setExpiredError(null)
    setState({ kind: 'authenticated', user })
  }, [])
  // After Sign out and whenever the API answers 401 (session gone).
  const handleSignedOut = useCallback(() => {
    setFocusLogin(true)
    setSigningOut(false)
    setSignOutError(null)
    setExpiredError(null)
    setState({ kind: 'anonymous' })
  }, [])
  const handleUnauthorized = useCallback(() => {
    handleSignedOut()
    setExpiredError(describeError(new UnauthorizedError()))
  }, [handleSignedOut])

  async function handleSignOut() {
    if (signingOut) return
    setSigningOut(true)
    setSignOutError(null)
    try {
      await logout()
    } catch (error) {
      // A 401 means the session is already gone, which is what Sign out wants.
      if (!(error instanceof UnauthorizedError)) {
        setSignOutError(describeError(error, 'write'))
        setSigningOut(false)
        return
      }
    }
    handleSignedOut()
  }

  const user = state.kind === 'authenticated' ? state.user : null
  const session = useMemo<Session | null>(
    () => (user === null ? null : { user, onUnauthorized: handleUnauthorized }),
    [user, handleUnauthorized],
  )

  function retry() {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }

  const shell = (
    <AppShell
      user={user}
      onSignOut={handleSignOut}
      signingOut={signingOut}
      nav={user !== null ? <AppNav /> : undefined}
      crumb={user !== null ? <SectionCrumb /> : undefined}
    >
      {state.kind === 'loading' && <p className="text-muted-foreground">{t('app.loading')}</p>}
      {state.kind === 'error' && (
        <Card role="alert" className="gap-0 rounded-lg py-5 shadow-none">
          <CardContent className="grid justify-items-start gap-3">
            <p className="text-destructive">
              {errorMessage(state.error, t)}
            </p>
            <Button type="button" variant="outline" onClick={retry}>
              {t('app.retry')}
            </Button>
          </CardContent>
        </Card>
      )}
      {state.kind === 'anonymous' && (
        <>
          {expiredError && <p className="text-destructive" role="alert">{errorMessage(expiredError, t)}</p>}
          <LoginForm onSignedIn={handleSignedIn} focusHeading={focusLogin} />
        </>
      )}
      {state.kind === 'authenticated' && signOutError && (
        <p className="text-destructive" role="alert">
          {errorMessage(signOutError, t)}
        </p>
      )}
      {session !== null && <Outlet />}
    </AppShell>
  )

  if (session !== null && user !== null) {
    return (
      <SessionContext.Provider value={session}>
        <SupervisorQueueProvider user={user} onUnauthorized={handleUnauthorized}>
          {shell}
        </SupervisorQueueProvider>
      </SessionContext.Provider>
    )
  }
  return shell
}

export default App
