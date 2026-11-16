import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type {
  AgentResult,
  Capability,
  HistorySignal,
  OrchestrationStatus,
  OrchestrationView,
  SubstituteConsent,
  SupplierDelivery,
  TaskOutcome,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import { deadlineText, errorMessage, formatDate } from './format'

type Props = {
  inquiryId: number
  // null while the exception has not been orchestrated yet.
  orchestration: OrchestrationView | null
  // True while the panel analyzes, saves or re-runs the checks or the orchestrator.
  disabled: boolean
  // True while the panel re-runs the orchestrator.
  running: boolean
  // Re-runs the orchestrator and shows the result; rejects when the re-run failed.
  onRerun: () => Promise<void>
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Every status is shown as text; the tone only adds the colour.
type Tone = 'ok' | 'warn' | 'error' | 'muted'

const STATUS_TONE: Record<OrchestrationStatus, Tone> = {
  completed: 'ok',
  partial: 'warn',
  failed: 'error',
}

// A readable name for each check the orchestrator can run; an unknown one reads as a
// generic "additional check".
const CAPABILITY_KEY = {
  'substitute-compatibility': 'orchestration.capability.substituteCompatibility',
  'substitute-availability': 'orchestration.capability.substituteAvailability',
  'supplier-availability': 'orchestration.capability.supplierAvailability',
  'customer-history': 'orchestration.capability.customerHistory',
} as const satisfies Record<Capability, string>

const CONSENT_KEY = {
  confirmed: 'orchestration.consent.confirmed',
  refused: 'orchestration.consent.refused',
  unconfirmed: 'orchestration.consent.unconfirmed',
} as const satisfies Record<SubstituteConsent, string>

const SIGNAL_KEY = {
  accepted_before: 'orchestration.signal.accepted_before',
  declined_before: 'orchestration.signal.declined_before',
  mixed: 'orchestration.signal.mixed',
  no_substitute_history: 'orchestration.signal.no_substitute_history',
} as const satisfies Record<HistorySignal, string>

function covers(value: boolean, t: TFunction): string {
  return value ? t('orchestration.covers') : t('orchestration.coversNot')
}

function deliveryText(offer: SupplierDelivery, t: TFunction): string {
  return t('orchestration.delivery', {
    supplier: offer.supplier,
    quantity: offer.quantity,
    date: offer.available_on,
    lead: t('orchestration.days', { count: offer.lead_time_days }),
    deadline: deadlineText(offer.meets_deadline, t),
    covers: covers(offer.covers_shortage, t),
  })
}

// The short outcome of one agent, one line per candidate or offer.
function resultLines(result: AgentResult, t: TFunction): string[] {
  switch (result.capability) {
    case 'substitute-compatibility':
      if (result.candidates.length === 0) return [t('orchestration.noSubstitute')]
      return result.candidates.map((candidate) =>
        t('orchestration.substituteCompat', {
          code: candidate.code,
          name: candidate.name,
          compatibility: t(`orchestration.compatibility.${candidate.compatibility}`),
        }),
      )
    case 'substitute-availability':
      if (result.candidates.length === 0) return [t('orchestration.noSubstituteToCheck')]
      return result.candidates.map((candidate) =>
        t('orchestration.substituteStock', {
          code: candidate.code,
          stock: candidate.stock,
          covers: covers(candidate.covers_shortage, t),
        }),
      )
    case 'supplier-availability':
      if (result.offers.length === 0) return [t('orchestration.noSupplierOffer')]
      return result.offers.map((offer) => deliveryText(offer, t))
    case 'customer-history':
      return [
        t('orchestration.history', {
          orders: t('orchestration.orders', { count: result.orders_count }),
          accepted: result.substitutes_accepted,
          offered: result.substitutes_offered,
          signal: t(SIGNAL_KEY[result.signal]),
        }),
      ]
  }
}

function TaskItem({ task }: { task: TaskOutcome }) {
  const { t } = useTranslation()
  const completed = task.status === 'completed'
  return (
    <li className="check">
      <p className="check__head">
        <span className="check__name">
          {Object.hasOwn(CAPABILITY_KEY, task.capability)
            ? t(CAPABILITY_KEY[task.capability])
            : t('orchestration.capability.other')}
        </span>
        <span className={`check__status check__status--${completed ? 'ok' : 'muted'}`}>
          {completed ? t('orchestration.task.completed') : t('orchestration.task.unavailable')}
        </span>
      </p>
      {task.status === 'failed' && <p className="checks__line">{t('orchestration.task.failed')}</p>}
      {task.status === 'skipped' && (
        <p className="checks__line">{t('orchestration.task.skipped')}</p>
      )}
      {task.result !== null && (
        <dl className="metrics__list">
          <dt>{t('orchestration.result')}</dt>
          <dd>
            {resultLines(task.result, t).map((line) => (
              <span key={line} className="orchestration__result">
                {line}
              </span>
            ))}
          </dd>
        </dl>
      )}
    </li>
  )
}

// What the additional checks of an exception found; how they were planned and what they cost
// is in the run inspector.
function OrchestrationSection({
  inquiryId,
  orchestration,
  disabled,
  running,
  onRerun,
  onUnauthorized,
}: Props) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const headingId = `orchestration-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure, t))
    }
  }

  const offerRerun =
    orchestration === null || orchestration.stale || orchestration.status !== 'completed'

  return (
    <section className="orchestration" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        {t('orchestration.heading')}
      </h4>

      {orchestration === null && <p className="checks__line">{t('orchestration.notRun')}</p>}
      {orchestration?.stale && <p className="checks__line">{t('orchestration.stale')}</p>}
      {offerRerun && (
        <div className="analysis__actions">
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {running ? t('orchestration.running') : t('orchestration.rerun')}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">{t('orchestration.rerunFailed', { message: error })}</p>
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {orchestration !== null && (
        <OrchestrationResult inquiryId={inquiryId} orchestration={orchestration} />
      )}
    </section>
  )
}

function OrchestrationResult({
  inquiryId,
  orchestration,
}: {
  inquiryId: number
  orchestration: OrchestrationView
}) {
  const { t } = useTranslation()
  const tone = STATUS_TONE[orchestration.status]
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="checks__outcome">{t(`orchestration.status.${orchestration.status}`)}</p>
        <p className="checks__line">{t(CONSENT_KEY[orchestration.consent])}</p>
        {orchestration.consent === 'unconfirmed' && (
          <p className="orchestration__consent">{t('orchestration.consentWarning')}</p>
        )}
      </div>
      <p className="analysis__meta">
        {t('orchestration.orchestrated', {
          date: formatDate(orchestration.orchestrated_at),
        })}
      </p>

      {orchestration.error !== null && (
        <div className="orchestration__error">
          <p className="checks__line">{t('orchestration.failed')}</p>
          <Link
            to="/inquiries/$inquiryId/run"
            params={{ inquiryId: String(inquiryId) }}
            className="checks__line text-primary underline underline-offset-4"
          >
            {t('orchestration.details')}
          </Link>
        </div>
      )}

      {orchestration.tasks.length > 0 && (
        <ul className="checks__list" aria-label={t('orchestration.findings')}>
          {[...orchestration.tasks]
            .sort((a, b) => a.stage - b.stage)
            .map((task) => (
              <TaskItem key={task.capability} task={task} />
            ))}
        </ul>
      )}
    </>
  )
}

export default OrchestrationSection
