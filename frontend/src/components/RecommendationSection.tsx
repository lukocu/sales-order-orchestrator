import { useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { OrchestrationView, RecommendationView } from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate } from './format'
import VariantComparison from './VariantComparison'
import { variantName } from './variantName'

type Props = {
  inquiryId: number
  // null while there is no recommendation for the current orchestration.
  recommendation: RecommendationView | null
  // The orchestration the recommendation is built from; tells why there is none.
  orchestration: OrchestrationView | null
  // True while the panel analyzes, saves or re-runs the checks, the orchestrator or the
  // recommendation.
  disabled: boolean
  // True while the panel re-runs the recommendation.
  running: boolean
  // Re-runs the recommendation and shows the result; rejects when the re-run failed.
  onRerun: () => Promise<void>
  // True when re-running the recommendation is the step's primary action (outline otherwise).
  primary?: boolean
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
  // The inquiry's deadline (ISO date); null when it has none.
  expectedDeadline: string | null
}

// Why there cannot be a (current) recommendation; null when the orchestration allows one.
function blockedReason(orchestration: OrchestrationView | null, t: TFunction): string | null {
  if (orchestration === null) return t('recommendation.blocked.notOrchestrated')
  if (orchestration.status === 'failed') return t('recommendation.blocked.orchestrationFailed')
  if (orchestration.stale) return t('recommendation.blocked.orchestrationStale')
  return null
}

// The options of fulfilling the exception and the recommended one and why; the recommender and
// the run's cost are in the run inspector.
function RecommendationSection({
  inquiryId,
  recommendation,
  orchestration,
  disabled,
  running,
  onRerun,
  primary = false,
  onUnauthorized,
  expectedDeadline,
}: Props) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const headingId = `recommendation-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure, t))
    }
  }

  const blocked = blockedReason(orchestration, t)
  const outdated =
    recommendation === null || recommendation.stale || recommendation.status === 'failed'
  const offerRerun = blocked === null && outdated

  return (
    <section className="orchestration recommendation" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        {t('recommendation.heading')}
      </h4>

      {blocked !== null && (recommendation === null || recommendation.stale) && (
        <p className="checks__line">{blocked}</p>
      )}
      {blocked === null && recommendation === null && (
        <p className="checks__line">{t('recommendation.notRun')}</p>
      )}
      {recommendation?.stale && <p className="checks__line">{t('recommendation.stale')}</p>}
      {offerRerun && (
        <div className="analysis__actions">
          <Button
            type="button"
            variant={primary ? 'default' : 'outline'}
            onClick={rerun}
            disabled={disabled}
          >
            {running ? t('recommendation.running') : t('recommendation.rerun')}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">{t('recommendation.rerunFailed', { message: error })}</p>
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {recommendation !== null && (
        <RecommendationResult recommendation={recommendation} expectedDeadline={expectedDeadline} />
      )}
    </section>
  )
}

function RecommendationResult({
  recommendation,
  expectedDeadline,
}: {
  recommendation: RecommendationView
  expectedDeadline: string | null
}) {
  const { t } = useTranslation()
  const choice = recommendation.choice
  const chosen =
    recommendation.status === 'completed' && choice !== null
      ? (recommendation.options.find((option) => option.id === choice.option_id) ?? null)
      : null
  const completed = recommendation.status === 'completed'

  return (
    <>
      <div className={`checks__banner orchestration__banner--${completed ? 'ok' : 'error'}`}>
        <p className="checks__outcome">
          {completed ? t('recommendation.resultCompleted') : t('recommendation.resultFailed')}
        </p>
      </div>
      <p className="analysis__meta">
        {t('recommendation.recommended', {
          date: formatDate(recommendation.recommended_at),
        })}
      </p>

      {recommendation.error !== null && (
        <p className="orchestration__error checks__line">{t('recommendation.failed')}</p>
      )}

      {chosen !== null && choice !== null && (
        <div className="grid gap-1">
          <p className="text-base font-semibold">{variantName(chosen, t)}</p>
          <p className="text-sm font-semibold">{t('recommendation.why')}</p>
          <p className="checks__line">{choice.justification}</p>
        </div>
      )}

      {recommendation.options.length === 0 ? (
        <p className="checks__line">{t('recommendation.noOptions')}</p>
      ) : (
        <VariantComparison recommendation={recommendation} expectedDeadline={expectedDeadline} />
      )}
    </>
  )
}

export default RecommendationSection
