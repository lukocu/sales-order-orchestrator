import { act, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import type { PolicyResult, RecommendationView } from '../api/analysis'
import type { SupervisorReview } from '../api/supervisor'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'
import { ACME_EDITED_DRAFT, DELTA_AWAITING, DELTA_SUPERVISOR_REJECTED } from '../test/replyDraftFixtures'
import { ACME_ORCHESTRATION } from '../test/orchestrationFixtures'
import { renderWithRouter } from '../test/renderWithRouter'
import { SUPERVISOR } from '../test/userFixtures'
import PolicySection from './PolicySection'
import RecommendationSection from './RecommendationSection'

const offerPolicy: PolicyResult = {
  ...ACME_POLICY,
  rules: [{ ...ACME_POLICY.rules[1], verdict: 'fail', reason_code: 'offered_discount_above_maximum', reason: 'Producer detail must not drive translation' }],
  outcome: 'requires_supervisor',
}

it('switches the edited offer policy without replacing it with the current recommendation verdict', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const draft = { ...ACME_EDITED_DRAFT, policy: offerPolicy }
  const before = structuredClone(draft)
  render(<PolicySection inquiryId={7} policy={ACME_POLICY} recommendation={ACME_RECOMMENDATION}
    draft={draft} disabled={false} running={false} onRerun={vi.fn()} onUnauthorized={vi.fn()} />)
  expect(screen.getByRole('table')).toHaveTextContent('Offered discount above the maximum')
  await act(async () => { await i18n.changeLanguage('pl') })
  expect(screen.getByRole('table')).toHaveTextContent('Rabat w edytowanej ofercie przekracza maksimum')
  expect(screen.getByRole('table')).not.toHaveTextContent('Producer detail')
  expect(draft).toEqual(before)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('switches risk summaries and details while keeping the model justification original', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const recommendation: RecommendationView = {
    ...ACME_RECOMMENDATION,
    choice: { ...ACME_RECOMMENDATION.choice!, justification: 'Oryginalne uzasadnienie modelu' },
    options: [{ ...ACME_RECOMMENDATION.options[1], signals: [
      { code: 'incomplete_coverage', polarity: 'risk' as const, label: 'Old producer text', params: { covered: 50, requested: 80 } },
      { code: 'deadline_missed', polarity: 'risk' as const, label: 'Old date text', params: { fulfilled_on: '2026-11-09', deadline: '2026-11-06' } },
    ] }],
  }
  render(<RecommendationSection inquiryId={7} recommendation={recommendation} orchestration={ACME_ORCHESTRATION}
    disabled={false} running={false} onRerun={vi.fn()} onUnauthorized={vi.fn()} expectedDeadline="2026-11-06" />)
  expect(within(screen.getByRole('row', { name: /^Risks/ })).getByRole('cell')).toHaveTextContent('Covers 50 of 80 pcs')
  const details = document.querySelector('details')!
  expect(details).toHaveTextContent('Covers 50 of 80 pcs')
  expect(details).toHaveTextContent('9 Nov 2026')
  await act(async () => { await i18n.changeLanguage('pl') })
  expect(within(screen.getByRole('row', { name: /^Ryzyka/ })).getByRole('cell')).toHaveTextContent('Pokrywa 50 z 80 szt.')
  expect(details).toHaveTextContent('Pokrywa 50 z 80 szt.')
  expect(details).toHaveTextContent('9 lis 2026')
  expect(screen.getByText('Oryginalne uzasadnienie modelu')).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

describe('supervisor message localization', () => {
  it('switches attention and context descriptions without fetching or translating human content', async () => {
    const review: SupervisorReview = {
      inquiry_id: 17, sender_name: 'Customer', sender_email: 'buyer@example.com', subject: 'Original inquiry',
      body: 'Oryginalny mail klienta', received_at: '2026-11-18T10:00:00Z', draft_status: 'awaiting_supervisor',
      draft_updated_at: DELTA_AWAITING.updated_at, submitted_at: null, submitted_by: 2, review_state: 'actionable',
      allowed_actions: ['reject'], offer: DELTA_AWAITING.offer, offer_unavailable: false,
      offer_subject: 'Oryginalny temat szkicu', offer_body: 'Oryginalny szkic odpowiedzi', policy: offerPolicy,
      context: { fields: null, checks: null, orchestration: null, recommendation: null, policy: offerPolicy },
      decisions: [{ ...DELTA_SUPERVISOR_REJECTED, reason: 'Oryginalny komentarz człowieka' }],
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      const body = path === '/api/auth/me' ? SUPERVISOR
        : path === '/api/supervisor/queue' ? { items: [], total: 0 }
        : path === '/api/supervisor/reviews/17' ? review : null
      return new Response(JSON.stringify(body), { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)
    await renderWithRouter('/approvals/17')
    expect(await screen.findAllByText('Offered discount above the maximum')).toHaveLength(2)
    const calls = fetchMock.mock.calls.length
    await act(async () => { await i18n.changeLanguage('pl') })
    expect(screen.getAllByText('Rabat w edytowanej ofercie przekracza maksimum')).toHaveLength(2)
    for (const original of ['Oryginalny mail klienta', 'Oryginalny szkic odpowiedzi', 'Oryginalny komentarz człowieka']) {
      expect(screen.getByText(original)).toBeInTheDocument()
    }
    expect(fetchMock).toHaveBeenCalledTimes(calls)
  })
})