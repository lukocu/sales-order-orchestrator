import type {
  ParsedFields,
  PolicyResult,
  ReplyDraftDecision,
  ReplyDraftOffer,
  ReplyDraftStatus,
} from './analysis'
import { isPolicyResult, isReplyDraftStatus } from './analysis'
import { requestJson } from './client'

export type SupervisorQueueItem = {
  id: number
  sender_name: string
  customer?: string | null
  subject: string
  received_at: string
  submitted_at: string
  submitted_by: number | null
  draft_updated_at: string
  attention_rules: { code: 'margin' | 'discount' | 'order_value' | 'credit'; verdict: 'fail' | 'not_evaluated' }[]
  review_state: 'actionable' | 'stale' | 'unavailable'
}

export type SupervisorQueue = { items: SupervisorQueueItem[]; total: number }

export type SupervisorReview = {
  inquiry_id: number
  sender_name: string
  sender_email: string
  subject: string
  body: string
  received_at: string
  draft_status: ReplyDraftStatus | null
  draft_updated_at: string | null
  submitted_at: string | null
  submitted_by: number | null
  review_state: 'actionable' | 'stale' | 'unavailable' | 'not_awaiting'
  allowed_actions: ('approve' | 'reject')[]
  offer: ReplyDraftOffer | null
  offer_unavailable: boolean
  offer_subject: string | null
  offer_body: string | null
  policy: PolicyResult | null
  context: {
    fields: ParsedFields | null
    checks: unknown
    orchestration: Record<string, unknown> | null
    recommendation: Record<string, unknown> | null
    policy: PolicyResult | null
  }
  decisions: ReplyDraftDecision[]
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isQueueItem(value: unknown): value is SupervisorQueueItem {
  if (!object(value) || !Array.isArray(value.attention_rules)) return false
  return (
    typeof value.id === 'number' &&
    typeof value.sender_name === 'string' &&
    (value.customer === undefined || value.customer === null || typeof value.customer === 'string') &&
    typeof value.subject === 'string' &&
    typeof value.received_at === 'string' &&
    typeof value.submitted_at === 'string' &&
    (value.submitted_by === null || typeof value.submitted_by === 'number') &&
    typeof value.draft_updated_at === 'string' &&
    ['actionable', 'stale', 'unavailable'].includes(String(value.review_state)) &&
    value.attention_rules.every(
      (rule) =>
        object(rule) &&
        ['margin', 'discount', 'order_value', 'credit'].includes(String(rule.code)) &&
        ['fail', 'not_evaluated'].includes(String(rule.verdict)),
    )
  )
}

function isQueue(value: unknown): value is SupervisorQueue {
  return (
    object(value) &&
    typeof value.total === 'number' &&
    Array.isArray(value.items) &&
    value.items.every(isQueueItem)
  )
}

function isReview(value: unknown): value is SupervisorReview {
  if (!object(value) || !object(value.context)) return false
  return (
    typeof value.inquiry_id === 'number' &&
    typeof value.sender_name === 'string' &&
    typeof value.sender_email === 'string' &&
    typeof value.subject === 'string' &&
    typeof value.body === 'string' &&
    typeof value.received_at === 'string' &&
    (value.draft_status === null || isReplyDraftStatus(value.draft_status)) &&
    (value.draft_updated_at === null || typeof value.draft_updated_at === 'string') &&
    (value.submitted_at === null || typeof value.submitted_at === 'string') &&
    (value.submitted_by === null || typeof value.submitted_by === 'number') &&
    ['actionable', 'stale', 'unavailable', 'not_awaiting'].includes(String(value.review_state)) &&
    Array.isArray(value.allowed_actions) &&
    value.allowed_actions.every((action) => action === 'approve' || action === 'reject') &&
    Array.isArray(value.decisions) &&
    typeof value.offer_unavailable === 'boolean' &&
    (value.policy === null || isPolicyResult(value.policy)) &&
    (value.context.policy === undefined || value.context.policy === null || isPolicyResult(value.context.policy))
  )
}

export function fetchSupervisorQueue(signal?: AbortSignal): Promise<SupervisorQueue> {
  return requestJson('/api/supervisor/queue', isQueue, { signal })
}

export function fetchSupervisorReview(
  inquiryId: number,
  signal?: AbortSignal,
): Promise<SupervisorReview> {
  return requestJson(`/api/supervisor/reviews/${inquiryId}`, isReview, { signal })
}
