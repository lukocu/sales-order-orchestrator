import type { ReplyDraftAction, ReplyDraftStatus } from '../api/analysis'

// Every status is shown as text; the tone only adds the colour.
export type DraftTone = 'ok' | 'warn' | 'error'

// Labels are i18n keys, resolved with t() at render time.
export const STATUS = {
  draft: ['draft.status.draft', 'warn'],
  ready_to_send: ['draft.status.ready_to_send', 'ok'],
  awaiting_supervisor: ['draft.status.awaiting_supervisor', 'warn'],
  rejected: ['draft.status.rejected', 'error'],
} as const satisfies Record<ReplyDraftStatus, [string, DraftTone]>

export const ACTION_KEY = {
  edit: 'decisionHistory.action.edit',
  approve: 'decisionHistory.action.approve',
  reject: 'decisionHistory.action.reject',
  supervisor_approve: 'decisionHistory.action.supervisor_approve',
  supervisor_reject: 'decisionHistory.action.supervisor_reject',
} as const satisfies Record<ReplyDraftAction, string>
