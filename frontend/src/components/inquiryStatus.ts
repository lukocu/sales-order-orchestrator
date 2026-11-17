import type { Outcome, ReplyDraftStatus } from '../api/analysis'

// The one status an inquiry shows on the list and in the open inquiry's header.
export type InquiryStatus =
  | 'new'
  | 'analyzed'
  | 'exception'
  | 'needs_input'
  | 'awaiting_supervisor'
  | 'ready_to_send'
  | 'rejected'

export type InquiryStatusFacts = {
  analyzed: boolean
  outcome: Outcome | null
  draft_status: ReplyDraftStatus | null
}

// In priority order: a draft status outranks the outcome (a draft exists only for an
// exception); a stale draft keeps its raw status, as the "awaiting only" filter does.
// An analysis without a current outcome (none yet, or stale checks) is just "analysed".
export function inquiryStatus({ analyzed, outcome, draft_status }: InquiryStatusFacts): InquiryStatus {
  if (draft_status === 'awaiting_supervisor') return 'awaiting_supervisor'
  if (draft_status === 'ready_to_send') return 'ready_to_send'
  if (draft_status === 'rejected') return 'rejected'
  if (outcome === 'exception') return 'exception'
  if (outcome === 'needs_input') return 'needs_input'
  return analyzed ? 'analyzed' : 'new'
}

// Text and colour: the badge never relies on colour alone. Filled marks a pending or final
// state of the draft, outline marks an outcome of the checks.
export const STATUS_VARIANT = {
  new: 'outline',
  analyzed: 'success-outline',
  exception: 'destructive-outline',
  needs_input: 'warning-outline',
  awaiting_supervisor: 'warning',
  ready_to_send: 'success',
  rejected: 'destructive-outline',
} as const satisfies Record<InquiryStatus, string>
