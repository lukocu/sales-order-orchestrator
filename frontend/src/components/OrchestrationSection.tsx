import { useState } from 'react'
import { Link } from '@tanstack/react-router'
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
import { formatDate } from './format'

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

const CONSENT: Record<SubstituteConsent, string> = {
  confirmed: 'Substitute consent: confirmed',
  refused: 'Substitute consent: refused',
  unconfirmed: 'Substitute consent: not confirmed',
}

const SIGNAL: Record<HistorySignal, string> = {
  accepted_before: 'accepted substitutes before',
  declined_before: 'declined substitutes before',
  mixed: 'mixed substitute history',
  no_substitute_history: 'no substitute history',
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

function covers(value: boolean): string {
  return value ? 'covers the shortage' : 'does not cover the shortage'
}

function deadlineText(meets: boolean | null): string {
  if (meets === null) return 'no deadline'
  return meets ? 'meets the deadline' : 'misses the deadline'
}

function deliveryText(offer: SupplierDelivery): string {
  return (
    `${offer.supplier}: ${offer.quantity} pcs on ${offer.available_on} ` +
    `(${plural(offer.lead_time_days, 'day')}), ${deadlineText(offer.meets_deadline)}, ` +
    covers(offer.covers_shortage)
  )
}

// The short outcome of one agent, one line per candidate or offer.
function resultLines(result: AgentResult): string[] {
  switch (result.capability) {
    case 'substitute-compatibility':
      if (result.candidates.length === 0) return ['No substitute in the catalogue']
      return result.candidates.map(
        (candidate) =>
          `${candidate.code} ${candidate.name} — ${candidate.compatibility} compatibility`,
      )
    case 'substitute-availability':
      if (result.candidates.length === 0) return ['No substitute to check']
      return result.candidates.map(
        (candidate) =>
          `${candidate.code}: ${candidate.stock} in stock, ${covers(candidate.covers_shortage)}`,
      )
    case 'supplier-availability':
      if (result.offers.length === 0) return ['No supplier offer']
      return result.offers.map(deliveryText)
    case 'customer-history':
      return [
        `${plural(result.orders_count, 'order')}, substitutes accepted ` +
          `${result.substitutes_accepted} of ${result.substitutes_offered} offered — ` +
          SIGNAL[result.signal],
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
          <dt>Result</dt>
          <dd>
            {resultLines(task.result).map((line) => (
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
  const [error, setError] = useState<string | null>(null)
  const headingId = `orchestration-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure))
    }
  }

  const offerRerun =
    orchestration === null || orchestration.stale || orchestration.status !== 'completed'

  return (
    <section className="orchestration" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Orchestration
      </h4>

      {orchestration === null && <p className="checks__line">Orchestration not run yet</p>}
      {orchestration?.stale && (
        <p className="checks__line">
          The analysis changed after this orchestration ran; the result may be out of date.
        </p>
      )}
      {offerRerun && (
        <div className="analysis__actions">
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {running ? 'Running orchestrator…' : 'Re-run orchestrator'}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Re-running the orchestrator failed: {error}</p>
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            Retry
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
        <p className="checks__line">{CONSENT[orchestration.consent]}</p>
        {orchestration.consent === 'unconfirmed' && (
          <p className="orchestration__consent">
            Customer consent to a substitute not confirmed
          </p>
        )}
      </div>
      <p className="analysis__meta">Orchestrated {formatDate(orchestration.orchestrated_at)}</p>

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
