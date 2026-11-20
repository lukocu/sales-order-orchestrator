import type { Analysis } from '../api/analysis'

// The inquiry view is a four-step flow; the steps are derived from the analysis alone.
export type StepId = 'inquiry' | 'variants' | 'approval' | 'reply'

// done: finished and open for review; active: where the flow stands; locked: not reachable yet;
// not_needed: the inquiry is standard, so the step does not apply.
export type StepState = 'done' | 'active' | 'locked' | 'not_needed'

export const STEP_ORDER: readonly StepId[] = ['inquiry', 'variants', 'approval', 'reply']

export type InquirySteps = {
  // The step the flow stands at (for a standard inquiry: the inquiry step, which is done).
  active: StepId
  states: Record<StepId, StepState>
}

function activeStep(analysis: Analysis | null): StepId {
  const checks = analysis?.checks ?? null
  if (analysis === null || checks === null || checks.stale || checks.outcome !== 'exception') {
    return 'inquiry'
  }
  const orchestration = analysis.orchestration
  const recommendation = analysis.recommendation ?? null
  if (
    orchestration === null ||
    orchestration.status !== 'completed' ||
    recommendation === null ||
    recommendation.status === 'failed' ||
    recommendation.stale
  ) {
    return 'variants'
  }
  const draft = analysis.draft ?? null
  if (draft === null || draft.stale || draft.status !== 'ready_to_send') return 'approval'
  return 'reply'
}

export function inquirySteps(analysis: Analysis | null): InquirySteps {
  const checks = analysis?.checks ?? null
  if (checks !== null && !checks.stale && checks.outcome === 'standard') {
    return {
      active: 'inquiry',
      states: { inquiry: 'done', variants: 'not_needed', approval: 'not_needed', reply: 'not_needed' },
    }
  }
  const active = activeStep(analysis)
  const activeIndex = STEP_ORDER.indexOf(active)
  const states = {} as Record<StepId, StepState>
  STEP_ORDER.forEach((step, index) => {
    states[step] = index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'locked'
  })
  return { active, states }
}

// The step id named in an address (`?step=variants`), or null for anything else.
export function parseStepId(value: unknown): StepId | null {
  return STEP_ORDER.find((step) => step === value) ?? null
}

// A done or active step can be viewed; a locked or not needed one cannot.
export function stepOpen(steps: InquirySteps, step: StepId): boolean {
  const state = steps.states[step]
  return state === 'done' || state === 'active'
}

// Where a link opens: the step it names if that step can be viewed, otherwise the active
// step. `fallback` says the link named a step (or an unknown value) that cannot be opened; a
// link without a step simply opens the active step.
export function resolveLinkedStep(
  requested: string | undefined,
  steps: InquirySteps,
): { step: StepId; fallback: boolean } {
  const step = parseStepId(requested)
  if (step !== null && stepOpen(steps, step)) return { step, fallback: false }
  return { step: steps.active, fallback: requested !== undefined }
}

export type StepBackKey =
  | 'steps.back.draftRejected'
  | 'steps.back.analysisReplaced'
  | 'steps.back.outdated'

// Why the flow went back, as an i18n key, or null when it did not (or there was nothing to
// go back from). A rejected draft keeps the flow at the approval step but is still announced.
export function stepBackReason(prev: Analysis | null, next: Analysis | null): StepBackKey | null {
  if (prev === null || next === null) return null
  const before = inquirySteps(prev).active
  const after = inquirySteps(next).active
  if (
    after === 'approval' &&
    next.draft?.status === 'rejected' &&
    prev.draft?.status !== 'rejected'
  ) {
    return 'steps.back.draftRejected'
  }
  if (STEP_ORDER.indexOf(after) >= STEP_ORDER.indexOf(before)) return null
  return prev.analyzed_at !== next.analyzed_at
    ? 'steps.back.analysisReplaced'
    : 'steps.back.outdated'
}
