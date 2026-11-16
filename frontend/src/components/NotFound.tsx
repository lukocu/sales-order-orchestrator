import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

// Unknown addresses and invalid inquiry ids (the root notFoundComponent and the inbox route).
function NotFound() {
  const { t } = useTranslation()

  return (
    <Card
      role="region"
      aria-labelledby="not-found-heading"
      className="gap-0 rounded-lg py-5 shadow-none"
    >
      <CardContent className="grid justify-items-start gap-3">
        <h2 id="not-found-heading" className="text-lg font-semibold">
          {t('notFound.heading')}
        </h2>
        <p className="text-muted-foreground">{t('notFound.body')}</p>
        <Button asChild variant="outline">
          <Link to="/" activeOptions={{ exact: true }} activeProps={{}}>
            {t('notFound.back')}
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}

export default NotFound
