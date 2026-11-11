import { useState } from 'react'
import type {
  ConfidenceBand,
  OptionKind,
  OptionLine,
  OrchestrationView,
  RecommendationError,
  RecommendationErrorKind,
  RecommendationOption,
  RecommendationView,
  RecommenderChoice,
  Signal,
  SignalPolarity,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { formatDate, formatPercent, formatPln } from './format'
import RunMetrics from './RunMetrics'

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

const KIND: Record<OptionKind, string> = {
  partial_delivery: 'Partial delivery from stock',
  substitute: 'Stock + substitute',
  other_source: 'Stock + supplier',
  combined: 'Stock + substitute + supplier',
}

const BAND: Record<ConfidenceBand, string> = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
}

const ERROR_KIND: Record<RecommendationErrorKind, string> = {
  recommender_failed: 'Recommender failed',
  choice_rejected: 'Choice rejected',
}

// Signal lists in this order; labels come from the backend, in Polish.
const POLARITIES: [SignalPolarity, string, string][] = [
  ['positive', 'Positive', '✓'],
  ['risk', 'Risks', '⚠'],
  ['info', 'Information', 'ℹ'],
]

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

// Why there cannot be a (current) recommendation; null when the orchestration allows one.
function blockedReason(orchestration: OrchestrationView | null): string | null {
  if (orchestration === null) return 'No recommendation: the exception is not orchestrated yet.'
  if (orchestration.status === 'failed') return 'No recommendation: the orchestration failed.'
  if (orchestration.stale) {
    return 'No recommendation: the orchestration is out of date; re-run the orchestrator first.'
  }
  return null
}

function sourceText(line: OptionLine): string {
  switch (line.source) {
    case 'stock':
      return 'own stock'
    case 'substitute_stock':
      return 'substitute from stock'
    case 'supplier':
      return `supplier ${line.supplier ?? '—'}`
  }
}

function lineText(line: OptionLine): string {
  return (
    `${line.quantity} × ${line.product_code} ${line.product_name} — ${sourceText(line)}, ` +
    `available ${line.available_on}, ${line.unit_price} PLN/pc`
  )
}

function deadlineText(meets: boolean | null): string {
  if (meets === null) return 'no deadline'
  return meets ? 'meets the deadline' : 'misses the deadline'
}

function SignalLists({ signals, cited }: { signals: Signal[]; cited: readonly string[] }) {
  return (
    <>
      {POLARITIES.map(([polarity, title, mark]) => {
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
                    {isCited && <span className="recommendation__cited-tag"> · cited</span>}
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
  return (
    <>
      <p className="check__head">
        <span className="check__name">{KIND[option.kind]}</span>
        <span className={`recommendation__band recommendation__band--${BAND[option.band]}`}>
          {option.band} confidence
        </span>
      </p>
      <dl className="metrics__list">
        <dt>Option</dt>
        <dd>{option.id}</dd>
        <dt>Lines</dt>
        <dd>
          {option.lines.map((line) => (
            <span key={`${line.source}-${line.product_code}`} className="orchestration__result">
              {lineText(line)}
            </span>
          ))}
        </dd>
        <dt>Coverage</dt>
        <dd>
          {option.covered_quantity} / {option.requested_quantity} pcs
        </dd>
        <dt>Fulfilled</dt>
        <dd>
          {option.fulfilled_on}, {deadlineText(option.meets_deadline)}
        </dd>
        <dt>Value</dt>
        <dd>{formatPln(option.value)}</dd>
        <dt>Cost</dt>
        <dd>{formatPln(option.cost)}</dd>
        <dt>Margin</dt>
        <dd>{formatPercent(option.margin_percent)}</dd>
      </dl>
      {justification !== undefined && (
        <>
          <p className="recommendation__why">Why this recommendation?</p>
          <p className="checks__line">{justification}</p>
        </>
      )}
      <SignalLists signals={option.signals} cited={cited} />
    </>
  )
}

function ErrorBox({
  error,
  choice,
}: {
  error: RecommendationError
  choice: RecommenderChoice | null
}) {
  return (
    <div className="orchestration__error">
      <p className="checks__outcome">
        {ERROR_KIND[error.kind]}: {error.code}
      </p>
      <p className="checks__line">{error.message}</p>
      {error.kind === 'choice_rejected' && choice !== null && (
        <p className="checks__line">Rejected choice: option {choice.option_id}</p>
      )}
    </div>
  )
}

// The options of fulfilling the exception, the recommended one and why, and the run's cost.
function RecommendationSection({
  inquiryId,
  recommendation,
  orchestration,
  disabled,
  running,
  onRerun,
  onUnauthorized,
}: Props) {
  const [error, setError] = useState<string | null>(null)
  const headingId = `recommendation-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure))
    }
  }

  const blocked = blockedReason(orchestration)
  const outdated =
    recommendation === null || recommendation.stale || recommendation.status === 'failed'
  const offerRerun = blocked === null && outdated

  return (
    <section className="orchestration recommendation" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Recommendation
      </h4>

      {blocked !== null && (recommendation === null || recommendation.stale) && (
        <p className="checks__line">{blocked}</p>
      )}
      {blocked === null && recommendation === null && (
        <p className="checks__line">Recommendation not run yet</p>
      )}
      {recommendation?.stale && (
        <p className="checks__line">
          The analysis, checks or orchestration changed after this recommendation ran; the
          result may be out of date.
        </p>
      )}
      {offerRerun && (
        <div className="analysis__actions">
          <button type="button" onClick={rerun} disabled={disabled}>
            {running ? 'Running recommendation…' : 'Re-run recommendation'}
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Re-running the recommendation failed: {error}</p>
          <button type="button" onClick={rerun} disabled={disabled}>
            Retry
          </button>
        </div>
      )}

      {recommendation !== null && <RecommendationResult recommendation={recommendation} />}
    </section>
  )
}

function RecommendationResult({ recommendation }: { recommendation: RecommendationView }) {
  const choice = recommendation.choice
  const chosen =
    recommendation.status === 'completed' && choice !== null
      ? (recommendation.options.find((option) => option.id === choice.option_id) ?? null)
      : null
  const others = recommendation.options.filter((option) => option !== chosen)
  const othersTitle = chosen === null ? 'Options' : 'Other options'
  const completed = recommendation.status === 'completed'

  return (
    <>
      <div
        className={`checks__banner orchestration__banner--${completed ? 'ok' : 'error'}`}
      >
        <p className="checks__outcome">
          Recommendation: {completed ? 'Completed' : 'Failed — no option chosen'}
        </p>
      </div>
      <p className="analysis__meta">
        Recommended {formatDate(recommendation.recommended_at)} · recommender{' '}
        {recommendation.recommender}
      </p>

      {recommendation.error !== null && (
        <ErrorBox error={recommendation.error} choice={choice} />
      )}

      {chosen !== null && choice !== null && (
        <section className="check recommendation__chosen" aria-label="Recommended option">
          <p className="orchestration__stage-title">Recommended option</p>
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
        <p className="checks__line">No option could be built from the orchestration results.</p>
      )}

      <RunMetrics run={recommendation.run} label="Recommendation metrics" />
    </>
  )
}

export default RecommendationSection
