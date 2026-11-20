import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { User } from '../api/auth'
import { Button } from '@/components/ui/button'
import LanguageSwitch from './LanguageSwitch'
import ThemeSwitch from './ThemeSwitch'

type Props = {
  user: User | null
  onSignOut?: () => void
  signingOut?: boolean
  // Sidebar navigation for signed-in users.
  nav?: ReactNode
  // The current section, shown after the product name in the top bar.
  crumb?: ReactNode
  children: ReactNode
}

// The product mark: a plain triangle in the text colour.
function Mark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4 shrink-0 fill-current">
      <path d="M12 2 2 22h20L12 2z" />
    </svg>
  )
}

function Brand() {
  const { t } = useTranslation()
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Mark />
      {/* One line: a name longer than the sidebar ends in an ellipsis, in full on hover. */}
      <h1 className="truncate text-sm font-semibold tracking-tight" title={t('app.title')}>
        {t('app.title')}
      </h1>
    </div>
  )
}

// One frame for every app state. Signed out: a top bar with the product name and the language
// switch over narrow content. Signed in: a sidebar with the product name and the navigation,
// a top bar with the section, the language switch, the user and Sign out, then wide content.
function AppShell({ user, onSignOut, signingOut = false, nav, crumb, children }: Props) {
  const { t } = useTranslation()

  if (user === null) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <header className="border-b bg-card">
          <div className="mx-auto box-content flex h-14 max-w-lg items-center justify-between gap-4 px-4">
            <Brand />
            <div className="flex items-center gap-3">
              <ThemeSwitch />
              <LanguageSwitch />
            </div>
          </div>
        </header>
        <main className="mx-auto box-content grid max-w-lg gap-6 px-4 py-10">{children}</main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground md:flex">
      <aside className="border-b bg-card md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col md:border-e md:border-b-0">
        <div className="flex h-14 items-center px-4 md:border-b">
          <Brand />
        </div>
        <div className="px-3 pb-3 md:py-3">{nav}</div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b bg-card px-4 py-2 md:px-6">
          <p className="flex items-center gap-1.5 text-sm">
            {/* The product name is already above the navigation on narrow screens. */}
            <span className="hidden text-muted-foreground md:inline">{t('app.title')}</span>
            {crumb != null && (
              <>
                <ChevronRight aria-hidden="true" className="hidden size-4 text-muted-foreground md:block" />
                {crumb}
              </>
            )}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <ThemeSwitch />
            <LanguageSwitch />
            <div className="flex items-center gap-3 border-s ps-4">
              <div className="text-end text-xs leading-tight">
                <p className="font-semibold">{user.display_name}</p>
                <p className="text-muted-foreground">{t(`role.${user.role}`)}</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground aria-disabled:pointer-events-none aria-disabled:opacity-50"
                onClick={signingOut ? undefined : onSignOut}
                aria-disabled={signingOut ? 'true' : undefined}
              >
                {signingOut ? t('inbox.signingOut') : t('inbox.signOut')}
              </Button>
            </div>
          </div>
        </header>
        <main className="grid flex-1 content-start gap-6 p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}

export default AppShell
