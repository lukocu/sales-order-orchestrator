import { useState } from 'react'
import type {
  AgentResult,
  HistorySignal,
  OrchestrationError,
  OrchestrationErrorKind,
  OrchestrationStatus,
  OrchestrationView,
  PlannerChoice,
  RunSummary,
  SubstituteConsent,
  SupplierDelivery,
  TaskOutcome,
  TaskStatus,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { formatDate, formatMs } from './format'
import RunMetrics from './RunMetrics'

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

const STATUS: Record<OrchestrationStatus, [string, Tone]> = {
  completed: ['Completed', 'ok'],
  partial: ['Partial — some checks failed', 'warn'],
  failed: ['Failed', 'error'],
}

const TASK_STATUS: Record<TaskStatus, [string, Tone]> = {
  completed: ['Completed', 'ok'],
  failed: ['Failed', 'error'],
  skipped: ['Skipped', 'muted'],
}

const CONSENT: Record<SubstituteConsent, string> = {
  confirmed: 'Substitute consent: confirmed',
  refused: 'Substitute consent: refused',
  unconfirmed: 'Substitute consent: not confirmed',
}

const ERROR_KIND: Record<OrchestrationErrorKind, string> = {
  planner_failed: 'Planner failed',
  plan_rejected: 'Plan rejected',
  capability_mismatch: 'Capability mismatch',
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

// Sum of the durations of the task's steps (one per attempt) in the orchestration run.
function taskDuration(task: TaskOutcome, run: RunSummary | null): string {
  if (run === null || task.steps.length === 0) return '—'
  const steps = run.steps.filter((step) => task.steps.includes(step.name))
  if (steps.length === 0) return '—'
  return formatMs(steps.reduce((sum, step) => sum + step.duration_ms, 0))
}

function stageTitle(stage: number, tasks: TaskOutcome[]): string {
  const after = [...new Set(tasks.flatMap((task) => task.depends_on))]
  const notes: string[] = []
  if (tasks.length > 1) notes.push('in parallel')
  if (after.length > 0) notes.push(`after: ${after.join(', ')}`)
  return notes.length === 0 ? `Stage ${stage}` : `Stage ${stage} — ${notes.join(', ')}`
}

function stagesOf(tasks: TaskOutcome[]): [number, TaskOutcome[]][] {
  const stages = new Map<number, TaskOutcome[]>()
  for (const task of tasks) stages.set(task.stage, [...(stages.get(task.stage) ?? []), task])
  return [...stages.entries()].sort(([a], [b]) => a - b)
}

function TaskItem({ task, run }: { task: TaskOutcome; run: RunSummary | null }) {
  const [status, tone] = TASK_STATUS[task.status]
  return (
    <li className="check">
      <p className="check__head">
        <span className="check__name">
          {task.capability} → {task.agent}
        </span>
        <span className={`check__status check__status--${tone}`}>{status}</span>
      </p>
      <dl className="metrics__list">
        <dt>Reason</dt>
        <dd>{task.reason}</dd>
        <dt>Attempts</dt>
        <dd>{task.steps.length}</dd>
        <dt>Duration</dt>
        <dd>{taskDuration(task, run)}</dd>
        {task.result !== null && (
          <>
            <dt>Result</dt>
            <dd>
              {resultLines(task.result).map((line) => (
                <span key={line} className="orchestration__result">
                  {line}
                </span>
              ))}
            </dd>
          </>
        )}
        {task.status === 'failed' && (
          <>
            <dt>Error</dt>
            <dd>{task.error_type ?? 'unknown'}</dd>
          </>
        )}
        {task.status === 'skipped' && (
          <>
            <dt>Skipped</dt>
            <dd>a prerequisite failed</dd>
          </>
        )}
      </dl>
    </li>
  )
}

function rejectedChoice(choice: PlannerChoice): string[] {
  return choice.tasks.map((task) => `${task.capability} — ${task.reason}`)
}

function ErrorBox({ error, choice }: { error: OrchestrationError; choice: PlannerChoice | null }) {
  return (
    <div className="orchestration__error">
      <p className="checks__outcome">
        {ERROR_KIND[error.kind]}: {error.code}
      </p>
      <p className="checks__line">{error.message}</p>
      {error.kind === 'plan_rejected' && choice !== null && (
        <>
          <p className="checks__line">Rejected planner choice:</p>
          <ul className="checks__reasons" aria-label="Rejected planner choice">
            {rejectedChoice(choice).map((line) => (
              <li key={line}>{line}</li>
            ))}
            {choice.tasks.length === 0 && <li>(no tasks)</li>}
          </ul>
        </>
      )}
    </div>
  )
}

function wallLine(run: RunSummary): string {
  const wall = run.duration_ms ?? run.totals.duration_ms
  const sum = formatMs(run.totals.steps_duration_ms)
  return `Wall time ${wall === null ? '—' : formatMs(wall)} · sum of steps ${sum}`
}

// What the orchestrator planned, which agent checked what, the outcome and the cost.
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
          <button type="button" onClick={rerun} disabled={disabled}>
            {running ? 'Running orchestrator…' : 'Re-run orchestrator'}
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Re-running the orchestrator failed: {error}</p>
          <button type="button" onClick={rerun} disabled={disabled}>
            Retry
          </button>
        </div>
      )}

      {orchestration !== null && <OrchestrationResult orchestration={orchestration} />}
    </section>
  )
}

function OrchestrationResult({ orchestration }: { orchestration: OrchestrationView }) {
  const [status, tone] = STATUS[orchestration.status]
  const run = orchestration.run
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="checks__outcome">Orchestration: {status}</p>
        <p className="checks__line">{CONSENT[orchestration.consent]}</p>
        {orchestration.consent === 'unconfirmed' && (
          <p className="orchestration__consent">
            Customer consent to a substitute not confirmed
          </p>
        )}
        {orchestration.planner_choice !== null && (
          <p className="checks__line">Planner: {orchestration.planner_choice.summary}</p>
        )}
      </div>
      <p className="analysis__meta">
        Orchestrated {formatDate(orchestration.orchestrated_at)} · planner {orchestration.planner}
      </p>

      {orchestration.error !== null && (
        <ErrorBox error={orchestration.error} choice={orchestration.planner_choice} />
      )}

      {stagesOf(orchestration.tasks).map(([stage, tasks]) => {
        const title = stageTitle(stage, tasks)
        return (
          <div key={stage} className="orchestration__stage">
            <p className="orchestration__stage-title">{title}</p>
            <ul className="checks__list" aria-label={title}>
              {tasks.map((task) => (
                <TaskItem key={task.capability} task={task} run={run} />
              ))}
            </ul>
          </div>
        )
      })}

      <RunMetrics run={run} label="Orchestration metrics" />
      {run !== null && <p className="analysis__meta">{wallLine(run)}</p>}
    </>
  )
}

export default OrchestrationSection
