import { describe, expect, it } from 'vitest'
import { inquiryStatus, type InquiryStatusFacts } from './inquiryStatus'

const NONE: InquiryStatusFacts = { analyzed: true, outcome: null, draft_status: null }

describe('inquiryStatus', () => {
  it.each<[string, InquiryStatusFacts, string]>([
    ['no analysis', { ...NONE, analyzed: false }, 'new'],
    ['an analysis without a current outcome', NONE, 'analyzed'],
    ['stale checks (no outcome) with an analysis', { ...NONE, outcome: null }, 'analyzed'],
    ['a standard outcome', { ...NONE, outcome: 'standard' }, 'analyzed'],
    ['an exception', { ...NONE, outcome: 'exception' }, 'exception'],
    ['an exception with a draft', { ...NONE, outcome: 'exception', draft_status: 'draft' }, 'exception'],
    ['needs input', { ...NONE, outcome: 'needs_input' }, 'needs_input'],
    [
      'a draft awaiting the supervisor',
      { ...NONE, outcome: 'exception', draft_status: 'awaiting_supervisor' },
      'awaiting_supervisor',
    ],
    [
      'a draft awaiting the supervisor, with the outcome gone stale',
      { ...NONE, outcome: null, draft_status: 'awaiting_supervisor' },
      'awaiting_supervisor',
    ],
    [
      'a draft ready to send',
      { ...NONE, outcome: 'exception', draft_status: 'ready_to_send' },
      'ready_to_send',
    ],
    ['a rejected draft', { ...NONE, outcome: 'exception', draft_status: 'rejected' }, 'rejected'],
  ])('%s is %s', (_, facts, expected) => {
    expect(inquiryStatus(facts)).toBe(expected)
  })
})
