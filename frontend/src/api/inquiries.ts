import {
  isOutcome,
  isReplyDraftStatus,
  type Outcome,
  type ReplyDraftStatus,
} from './analysis'
import { requestJson } from './client'

// Mirrors InquirySummary / InquiryDetail in backend/app/api/inquiries.py.
export type InquirySummary = {
  id: number
  sender_name: string
  sender_email: string
  subject: string
  received_at: string
  outcome: Outcome | null // of the check result, only while it is current
  draft_status: ReplyDraftStatus | null // of the inquiry's reply draft, null without one
}

export type InquiryDetail = InquirySummary & { body: string }

function isInquirySummary(value: unknown): value is InquirySummary {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.id === 'number' &&
    typeof v.sender_name === 'string' &&
    typeof v.sender_email === 'string' &&
    typeof v.subject === 'string' &&
    typeof v.received_at === 'string' &&
    (v.outcome === null || isOutcome(v.outcome)) &&
    (v.draft_status === null || isReplyDraftStatus(v.draft_status))
  )
}

function isInquiryList(value: unknown): value is InquirySummary[] {
  return Array.isArray(value) && value.every(isInquirySummary)
}

function isInquiryDetail(value: unknown): value is InquiryDetail {
  return isInquirySummary(value) && typeof (value as Record<string, unknown>).body === 'string'
}

// GET /api/inquiries: all inquiries, newest first (the backend orders them).
export function fetchInquiries(signal?: AbortSignal): Promise<InquirySummary[]> {
  return requestJson('/api/inquiries', isInquiryList, { signal })
}

// GET /api/inquiries/{id}: one inquiry with its body; unknown id → ApiError (404).
export function fetchInquiry(id: number, signal?: AbortSignal): Promise<InquiryDetail> {
  return requestJson(`/api/inquiries/${id}`, isInquiryDetail, { signal })
}
