import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { User } from '../api/auth'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import LanguageSwitch from './LanguageSwitch'

type Props = {
  user: User | null
  onSignOut?: () => void
  signingOut?: boolean
  // Navigation for later views (S-11, S-15); empty for now.
  nav?: ReactNode
  children: ReactNode
}

// One frame for every app state: the header with the product name, the language switch
// and, when signed in, the user and Sign out. Narrow content for sign-in, wide for the inbox.
function AppShell({ user, onSignOut, signingOut = false, nav, children }: Props) {
  const { t } = useTranslation()
  const width = user === null ? 'max-w-lg' : 'max-w-5xl'

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-card">
        <div
          className={cn(
            'mx-auto box-content flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3',
            width,
          )}
        >
          <h1 className="text-xl font-bold sm:text-2xl">{t('app.title')}</h1>
          {nav}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <LanguageSwitch />
            {user !== null && (
              <>
                <div className="text-sm leading-tight">
                  <p className="font-semibold">{user.display_name}</p>
                  <p className="text-muted-foreground">{t(`role.${user.role}`)}</p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onSignOut}
                  disabled={signingOut}
                >
                  {t('inbox.signOut')}
                </Button>
              </>
            )}
          </div>
        </div>
      </header>
      <main className={cn('mx-auto box-content grid gap-6 px-4 py-8', width)}>{children}</main>
    </div>
  )
}

export default AppShell
