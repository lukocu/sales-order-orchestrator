import { useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type {
  ConfidenceBand,
  OptionLine,
  OrchestrationView,
  RecommendationOption,
  RecommendationView,
  Signal,
  SignalPolarity,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import {
  deadlineText,
  errorMessage,
  formatDate,
  formatPercent,
  formatPln,
  sourceText,
} from './format'

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
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

const BAND: Record<ConfidenceBand, string> = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
}

// Signal lists in this order; the signal texts come from the backend, in Polish.
const POLARITIES: [SignalPolarity, string][] = [
  ['positive', '✓'],
  ['risk', '⚠'],
  ['info', 'ℹ'],
]

// Why there cannot be a (current) recommendation; null when the orchestration allows one.
function blockedReason(orchestration: OrchestrationView | null, t: TFunction): string | null {
  if (orchestration === null) return t('recommendation.blocked.notOrchestrated')
  if (orchestration.status === 'failed') return t('recommendation.blocked.orchestrationFailed')
  if (orchestration.stale) return t('recommendation.blocked.orchestrationStale')
  return null
}

function lineText(line: OptionLine, t: TFunction): string {
  return t('recommendation.line', {
    quantity: line.quantity,
    code: line.product_code,
    name: line.product_name,
    source: sourceText(line, t),
    date: line.available_on,
    price: line.unit_price,
  })
}

function SignalLists({ signals, cited }: { signals: Signal[]; cited: readonly string[] }) {
  const { t } = useTranslation()
  return (
    <>
      {POLARITIES.map(([polarity, mark]) => {
        const title = t(`recommendation.polarity.${polarity}`)
        const items = signals.filter((signal) => signal.polarity === polarity)
        if (items.length === 0) return null
        return (
          <div key={polarity} className="recommendation__signals">
            <p className="orchestration__stage-title">{title}</p>
            <ul
              className={`recommendation__signal-list recommendation__signal-list--${polarity}`}
              aria-label={title}
            >
              {items.map((signal) => {
                const isCited = cited.includes(signal.code)
                return (
                  <li key={signal.code} className={isCited ? 'recommendation__cited' : undefined}>
                    <span aria-hidden="true">{mark} </span>
                    {signal.label}
                    {isCited && (
                      <span className="recommendation__cited-tag">
                        {' · '}
                        {t('recommendation.cited')}
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}
    </>
  )
}

type OptionCardProps = {
  option: RecommendationOption
  // Signal codes the recommender cited; only for the recommended option.
  cited?: readonly string[]
  justification?: string
}

function OptionCard({ option, cited = [], justification }: OptionCardProps) {
  const { t } = useTranslation()
  return (
    <>
      <p className="check__head">
        <span className="check__name">{t(`optionKind.${option.kind}`)}</span>
        <span className={`recommendation__band recommendation__band--${BAND[option.band]}`}>
          {t(`recommendation.band.${option.band}`)}
        </span>
      </p>
      <dl className="metrics__list">
        <dt>{t('recommendation.lines')}</dt>
        <dd>
          {option.lines.map((line) => (
            <span key={`${line.source}-${line.product_code}`} className="orchestration__result">
              {lineText(line, t)}
            </span>
          ))}
        </dd>
        <dt>{t('recommendation.coverage')}</dt>
        <dd>
          {t('common.coverage', {
            covered: option.covered_quantity,
            requested: option.requested_quantity,
          })}
        </dd>
        <dt>{t('recommendation.fulfilled')}</dt>
        <dd>
          {t('recommendation.fulfilledOn', {
            date: option.fulfilled_on,
            deadline: deadlineText(option.meets_deadline, t),
          })}
        </dd>
        <dt>{t('recommendation.value')}</dt>
        <dd>{formatPln(option.value)}</dd>
        <dt>{t('recommendation.cost')}</dt>
        <dd>{formatPln(option.cost)}</dd>
        <dt>{t('recommendation.margin')}</dt>
        <dd>{formatPercent(option.margin_percent)}</dd>
      </dl>
      {justification !== undefined && (
        <>
          <p className="recommendation__why">{t('recommendation.why')}</p>
          <p className="checks__line">{justification}</p>
        </>
      )}
      <SignalLists signals={option.signals} cited={cited} />
    </>
  )
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
  onUnauthorized,
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
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
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

      {recommendation !== null && <RecommendationResult recommendation={recommendation} />}
    </section>
  )
}

function RecommendationResult({ recommendation }: { recommendation: RecommendationView }) {
  const { t } = useTranslation()
  const choice = recommendation.choice
  const chosen =
    recommendation.status === 'completed' && choice !== null
      ? (recommendation.options.find((option) => option.id === choice.option_id) ?? null)
      : null
  const others = recommendation.options.filter((option) => option !== chosen)
  const othersTitle =
    chosen === null ? t('recommendation.options') : t('recommendation.otherOptions')
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
        <section className="check recommendation__chosen" aria-label={t('recommendation.chosen')}>
          <p className="orchestration__stage-title">{t('recommendation.chosen')}</p>
          <OptionCard
            option={chosen}
            cited={choice.cited_signals}
            justification={choice.justification}
          />
        </section>
      )}

      {others.length > 0 && (
        <div className="orchestration__stage">
          <p className="orchestration__stage-title">{othersTitle}</p>
          <ul className="checks__list" aria-label={othersTitle}>
            {others.map((option) => (
              <li key={option.id} className="check">
                <OptionCard option={option} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {recommendation.options.length === 0 && (
        <p className="checks__line">{t('recommendation.noOptions')}</p>
      )}
    </>
  )
}

export default RecommendationSection
