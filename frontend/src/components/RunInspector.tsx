import { useId, type ReactNode, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import type {
  Analysis,
  OrchestrationView,
  RecommendationView,
  RunSummary,
  StepSummary,
  TaskOutcome,
} from '../api/analysis'
import { formatMs, formatUsd } from './format'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type Props = {
  // The analysis the inquiry view shows; null while loading or when there is none.
  analysis: Analysis | null
  loading: boolean
  open: boolean
  // Called when the user closes the Sheet (Esc, close button, overlay).
  onClose: () => void
  // Receives focus after the Sheet closes (on a cold open there is no trigger to return to).
  returnFocusTo?: RefObject<HTMLElement | null>
}

type T = ReturnType<typeof useTranslation>['t']

// --- Costs and durations ------------------------------------------------------------

function stepCostText(step: StepSummary, t: T): string {
  if (step.price_status === 'not_applicable') return '—'
  if (step.price_status === 'unpriced' || step.cost_usd === null) {
    return t('inspector.cost.notPriced')
  }
  return t('inspector.cost.listPrice', { amount: formatUsd(step.cost_usd) })
}

// The cost of one or more runs: the sum of their priced steps, marked incomplete when any
// run has an unpriced step.
function costText(runs: RunSummary[], t: T): string {
  const complete = runs.every((run) => run.totals.cost_complete)
  const anyPriced = runs.some((run) => run.steps.some((step) => step.price_status === 'priced'))
  if (!anyPriced) return complete ? '—' : t('inspector.cost.notPriced')
  const sum = runs.reduce((total, run) => total + Number(run.totals.cost_usd), 0)
  const cost = t('inspector.cost.listPrice', { amount: formatUsd(String(sum)) })
  return complete ? cost : t('inspector.cost.incomplete', { cost })
}

function runDurationMs(run: RunSummary): number {
  return run.totals.duration_ms ?? run.totals.steps_duration_ms
}

// Sum of the durations of the task's steps (one per attempt) in the orchestration run.
function taskDuration(task: TaskOutcome, run: RunSummary | null): string {
  if (run === null || task.steps.length === 0) return '—'
  const steps = run.steps.filter((step) => task.steps.includes(step.name))
  if (steps.length === 0) return '—'
  return formatMs(steps.reduce((sum, step) => sum + step.duration_ms, 0))
}

function stagesOf(tasks: TaskOutcome[]): [number, TaskOutcome[]][] {
  const stages = new Map<number, TaskOutcome[]>()
  for (const task of tasks) stages.set(task.stage, [...(stages.get(task.stage) ?? []), task])
  return [...stages.entries()].sort(([a], [b]) => a - b)
}

// --- Steps of one run -----------------------------------------------------------------

function StepStatus({ step }: { step: StepSummary }) {
  const { t } = useTranslation()
  if (step.status === 'ok') return <>{t('inspector.stepOk')}</>
  return (
    <span className="font-medium text-destructive">
      {step.error_type
        ? t('inspector.stepFailedWith', { error: step.error_type })
        : t('inspector.stepFailed')}
    </span>
  )
}

function RunSteps({ run, title }: { run: RunSummary; title: string }) {
  const { t } = useTranslation()
  const totals = run.totals
  return (
    <Table aria-label={t('inspector.stepsOf', { run: title })}>
      <TableHeader>
        <TableRow>
          <TableHead>{t('inspector.column.step')}</TableHead>
          <TableHead>{t('inspector.column.kind')}</TableHead>
          <TableHead>{t('inspector.column.model')}</TableHead>
          <TableHead className="text-right">{t('inspector.column.tokensIn')}</TableHead>
          <TableHead className="text-right">{t('inspector.column.tokensOut')}</TableHead>
          <TableHead>{t('inspector.column.cost')}</TableHead>
          <TableHead className="text-right">{t('inspector.column.duration')}</TableHead>
          <TableHead>{t('inspector.column.status')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {run.steps.map((step) => (
          <TableRow key={step.id}>
            <TableCell className="font-medium">{step.name}</TableCell>
            <TableCell>{t(`inspector.kind.${step.kind}`)}</TableCell>
            <TableCell>{step.model ?? '—'}</TableCell>
            <TableCell className="text-right tabular-nums">{step.input_tokens}</TableCell>
            <TableCell className="text-right tabular-nums">{step.output_tokens}</TableCell>
            <TableCell>{stepCostText(step, t)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatMs(step.duration_ms)}</TableCell>
            <TableCell>
              <StepStatus step={step} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={3}>{t('inspector.total')}</TableCell>
          <TableCell className="text-right tabular-nums">{totals.input_tokens}</TableCell>
          <TableCell className="text-right tabular-nums">{totals.output_tokens}</TableCell>
          <TableCell>{costText([run], t)}</TableCell>
          <TableCell className="text-right tabular-nums">{formatMs(runDurationMs(run))}</TableCell>
          <TableCell />
        </TableRow>
      </TableFooter>
    </Table>
  )
}

// --- Sections ---------------------------------------------------------------------------

type SectionProps = {
  title: string
  // False while the stage has not run for this inquiry.
  ran: boolean
  run: RunSummary | null
  // Shown above the steps: names of the components that ran, the plan, error codes.
  children?: ReactNode
}

function RunSection({ title, ran, run, children }: SectionProps) {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="grid min-w-0 gap-3">
      <h3 id={headingId} className="text-base font-semibold">
        {title}
      </h3>
      {!ran && <p className="text-sm text-muted-foreground">{t('inspector.notRun')}</p>}
      {ran && children}
      {ran && run === null && (
        <p className="text-sm text-muted-foreground">{t('inspector.noTrace')}</p>
      )}
      {ran && run !== null && <RunSteps run={run} title={title} />}
    </section>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  )
}

function TaskCard({ task, run }: { task: TaskOutcome; run: RunSummary | null }) {
  const { t } = useTranslation()
  const failed = task.status === 'failed'
  return (
    <li className="grid gap-2 rounded-md border bg-card p-3">
      <p className="font-medium">{task.capability}</p>
      <dl className="grid gap-1 text-sm">
        <Fact label={t('inspector.plan.agent')}>{task.agent}</Fact>
        <Fact label={t('inspector.plan.dependsOn')}>
          {task.depends_on.length === 0 ? t('inspector.plan.none') : task.depends_on.join(', ')}
        </Fact>
        <Fact label={t('inspector.plan.reason')}>{task.reason}</Fact>
        <Fact label={t('inspector.plan.status')}>
          <span className={failed ? 'font-medium text-destructive' : undefined}>
            {t(`inspector.taskStatus.${task.status}`)}
          </span>
        </Fact>
        <Fact label={t('inspector.plan.attempts')}>{task.steps.length}</Fact>
        <Fact label={t('inspector.plan.duration')}>{taskDuration(task, run)}</Fact>
        {failed && (
          <Fact label={t('inspector.plan.error')}>
            {task.error_type ?? t('inspector.plan.unknownError')}
          </Fact>
        )}
      </dl>
    </li>
  )
}

function Plan({ orchestration }: { orchestration: OrchestrationView }) {
  const { t } = useTranslation()
  const headingId = useId()
  const error = orchestration.error
  const choice = orchestration.planner_choice
  return (
    <section aria-labelledby={headingId} className="grid min-w-0 gap-3">
      <h4 id={headingId} className="text-sm font-semibold">
        {t('inspector.plan.heading')}
      </h4>
      <p className="text-sm">{t('inspector.plan.planner', { name: orchestration.planner })}</p>
      {choice !== null && (
        <p className="text-sm">{t('inspector.plan.summary', { summary: choice.summary })}</p>
      )}
      {error !== null && (
        <div className="grid gap-1 rounded-md border border-destructive p-3 text-sm">
          <p className="font-medium text-destructive">
            {t('inspector.errorCode', {
              kind: t(`inspector.errorKind.${error.kind}`),
              code: error.code,
            })}
          </p>
          <p className="text-muted-foreground">{error.message}</p>
          {error.kind === 'plan_rejected' && choice !== null && (
            <>
              <p>{t('inspector.plan.rejectedChoice')}</p>
              <ul className="list-disc pl-5" aria-label={t('inspector.plan.rejectedChoice')}>
                {choice.tasks.map((task) => (
                  <li key={task.capability}>
                    {task.capability} — {task.reason}
                  </li>
                ))}
                {choice.tasks.length === 0 && <li>{t('inspector.plan.noRejectedTasks')}</li>}
              </ul>
            </>
          )}
        </div>
      )}
      {orchestration.tasks.length === 0 && (
        <p className="text-sm text-muted-foreground">{t('inspector.plan.noTasks')}</p>
      )}
      {stagesOf(orchestration.tasks).map(([stage, tasks]) => {
        const title =
          tasks.length > 1
            ? `${t('inspector.plan.stage', { stage })} · ${t('inspector.plan.parallel')}`
            : t('inspector.plan.stage', { stage })
        return (
          <div key={stage} className="grid gap-2">
            <p className="text-sm font-semibold">{title}</p>
            <ul className="grid gap-2" aria-label={title}>
              {tasks.map((task) => (
                <TaskCard key={task.capability} task={task} run={orchestration.run} />
              ))}
            </ul>
          </div>
        )
      })}
    </section>
  )
}

function RecommenderLine({ recommendation }: { recommendation: RecommendationView }) {
  const { t } = useTranslation()
  const error = recommendation.error
  return (
    <>
      <p className="text-sm">{t('inspector.recommender', { name: recommendation.recommender })}</p>
      {error !== null && (
        <div className="grid gap-1 rounded-md border border-destructive p-3 text-sm">
          <p className="font-medium text-destructive">
            {t('inspector.errorCode', {
              kind: t(`inspector.errorKind.${error.kind}`),
              code: error.code,
            })}
          </p>
          <p className="text-muted-foreground">{error.message}</p>
        </div>
      )}
    </>
  )
}

function GrandTotal({ runs }: { runs: RunSummary[] }) {
  const { t } = useTranslation()
  const headingId = useId()
  const input = runs.reduce((sum, run) => sum + run.totals.input_tokens, 0)
  const output = runs.reduce((sum, run) => sum + run.totals.output_tokens, 0)
  const duration = runs.reduce((sum, run) => sum + runDurationMs(run), 0)
  return (
    <section
      aria-labelledby={headingId}
      className="grid min-w-0 gap-2 rounded-md border bg-card p-3"
    >
      <h3 id={headingId} className="text-base font-semibold">
        {t('inspector.grandTotal.heading')}
      </h3>
      <dl className="grid gap-1 text-sm">
        <Fact label={t('inspector.grandTotal.tokens')}>
          {t('inspector.grandTotal.tokensValue', { input, output })}
        </Fact>
        <Fact label={t('inspector.grandTotal.cost')}>{costText(runs, t)}</Fact>
        <Fact label={t('inspector.grandTotal.duration')}>{formatMs(duration)}</Fact>
      </dl>
    </section>
  )
}

function Runs({ analysis }: { analysis: Analysis }) {
  const { t } = useTranslation()
  const checks = analysis.checks
  const orchestration = analysis.orchestration
  const recommendation = analysis.recommendation ?? null
  const policy = analysis.policy ?? null
  const draft = analysis.draft ?? null
  const runs = [
    analysis.run,
    checks?.run ?? null,
    orchestration?.run ?? null,
    recommendation?.run ?? null,
    policy?.run ?? null,
    draft?.run ?? null,
  ].filter((run): run is RunSummary => run !== null)

  return (
    <>
      <RunSection title={t('inspector.section.parsing')} ran run={analysis.run}>
        <p className="text-sm">{t('inspector.extractor', { name: analysis.extractor })}</p>
        {analysis.extractor === 'fake' && (
          <p className="text-sm text-muted-foreground">{t('inspector.demoParser')}</p>
        )}
      </RunSection>
      <RunSection title={t('inspector.section.checks')} ran={checks !== null} run={checks?.run ?? null} />
      <RunSection
        title={t('inspector.section.orchestration')}
        ran={orchestration !== null}
        run={orchestration?.run ?? null}
      >
        {orchestration !== null && <Plan orchestration={orchestration} />}
      </RunSection>
      <RunSection
        title={t('inspector.section.recommendation')}
        ran={recommendation !== null}
        run={recommendation?.run ?? null}
      >
        {recommendation !== null && <RecommenderLine recommendation={recommendation} />}
      </RunSection>
      <RunSection title={t('inspector.section.policy')} ran={policy !== null} run={policy?.run ?? null} />
      <RunSection title={t('inspector.section.draft')} ran={draft !== null} run={draft?.run ?? null} />
      <GrandTotal runs={runs} />
    </>
  )
}

// The technical layer of one inquiry: the orchestrator plan, every run's steps and totals,
// and a grand total. Rendered by the inquiry view from the analysis it already holds.
function RunInspector({ analysis, loading, open, onClose, returnFocusTo }: Props) {
  const { t } = useTranslation()
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <SheetContent
        side="right"
        closeLabel={t('inspector.close')}
        className="w-full gap-0 overflow-y-auto sm:max-w-3xl"
        onCloseAutoFocus={(event) => {
          const target = returnFocusTo?.current
          if (!target) return
          event.preventDefault()
          target.focus()
        }}
      >
        <SheetHeader className="border-b pr-12">
          <SheetTitle className="text-lg">{t('inspector.title')}</SheetTitle>
          <SheetDescription>{t('inspector.description')}</SheetDescription>
        </SheetHeader>
        <div className="grid min-w-0 gap-6 p-4">
          {loading && (
            <p role="status" className="text-sm text-muted-foreground">
              {t('inspector.loading')}
            </p>
          )}
          {!loading && analysis === null && (
            <p className="text-sm text-muted-foreground">{t('inspector.noAnalysis')}</p>
          )}
          {!loading && analysis !== null && <Runs analysis={analysis} />}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default RunInspector
