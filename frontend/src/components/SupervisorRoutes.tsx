import type { ReactNode } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { useSession } from '../session'
import { Card, CardContent } from '@/components/ui/card'
import NotFound from './NotFound'
import SupervisorQueue from './SupervisorQueue'
import SupervisorReview from './SupervisorReview'

function SupervisorOnly({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { user } = useSession()
  if (user.role === 'supervisor') return children
  return (
    <Card className="gap-0 rounded-lg shadow-none">
      <CardContent className="grid justify-items-start gap-3 p-5">
        <h2 className="text-lg font-semibold">{t('supervisor.access.denied')}</h2>
        <p className="text-muted-foreground">{t('supervisor.access.explanation')}</p>
        <Link to="/" className="text-primary underline underline-offset-4">{t('supervisor.access.inbox')}</Link>
      </CardContent>
    </Card>
  )
}

export function SupervisorQueueRoute() {
  return <SupervisorOnly><SupervisorQueue /></SupervisorOnly>
}

function parseId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) && id > 0 ? id : null
}

export function SupervisorReviewRoute({ inspectorOpen = false }: { inspectorOpen?: boolean }) {
  const { inquiryId: rawId } = useParams({ strict: false })
  const id = parseId(rawId)
  if (id === null) return <NotFound />
  return <SupervisorOnly><SupervisorReview key={id} inquiryId={id} inspectorOpen={inspectorOpen} /></SupervisorOnly>
}
