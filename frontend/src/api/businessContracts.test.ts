import { describe, expect, it, vi } from 'vitest'
import { isPolicyResult, isPolicyView, isRecommendationView } from './analysis'
import { fetchSupervisorReview } from './supervisor'
import { ACME_POLICY } from '../test/policyFixtures'
import { ACME_RECOMMENDATION } from '../test/recommendationFixtures'

function policyWith(reasonCode: unknown) {
  return { ...ACME_POLICY, rules: [{ ...ACME_POLICY.rules[0], reason_code: reasonCode }] }
}

function recommendationWith(params: unknown) {
  const option = ACME_RECOMMENDATION.options[0]
  return { ...ACME_RECOMMENDATION, options: [{ ...option, signals: [{ ...option.signals[0], params }] }] }
}

describe('business message metadata at API boundaries', () => {
  it('accepts legacy policy without metadata and new nullable or unknown codes', () => {
    expect(isPolicyView(ACME_POLICY)).toBe(true)
    expect(isPolicyResult(ACME_POLICY)).toBe(true)
    for (const code of [undefined, null, 'margin_within_minimum', 'future_reason']) {
      expect(isPolicyView(policyWith(code))).toBe(true)
      expect(isPolicyResult(policyWith(code))).toBe(true)
    }
  })

  it.each([42, true, {}, []])('rejects malformed reason_code %j in stage and nested policy', (code) => {
    expect(isPolicyView(policyWith(code))).toBe(false)
    expect(isPolicyResult(policyWith(code))).toBe(false)
  })

  it('accepts absent, empty and scalar signal params without changing original payload', () => {
    expect(isRecommendationView(ACME_RECOMMENDATION)).toBe(true)
    for (const params of [undefined, {}, { covered: 50, requested: 80, product_code: 'ABC-110', fraction: 1.5 }]) {
      const payload = recommendationWith(params)
      const before = structuredClone(payload)
      expect(isRecommendationView(payload)).toBe(true)
      expect(payload).toEqual(before)
    }
  })

  it.each([null, [], true, 'params', { count: true }, { count: null }, { count: [] }, { nested: {} }, { count: NaN }, { count: Infinity }])(
    'rejects malformed signal params %j', (params) => {
      expect(isRecommendationView(recommendationWith(params))).toBe(false)
    },
  )

  it.each(['policy', 'context.policy'])('validates metadata in supervisor %s', async (position) => {
    const valid = {
      inquiry_id: 7, sender_name: 'Customer', sender_email: 'buyer@example.com', subject: 'Inquiry',
      body: 'Original email', received_at: '2026-11-18T10:00:00Z', draft_status: 'awaiting_supervisor',
      draft_updated_at: '2026-11-18T10:00:00Z', submitted_at: null, submitted_by: 2,
      review_state: 'actionable', allowed_actions: ['reject'], offer: null, offer_unavailable: true,
      offer_subject: null, offer_body: null, policy: ACME_POLICY,
      context: { fields: null, checks: null, orchestration: null, recommendation: null, policy: ACME_POLICY },
      decisions: [],
    }
    const reply = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
    const invalid = position === 'policy'
      ? { ...valid, policy: policyWith(42) }
      : { ...valid, context: { ...valid.context, policy: policyWith(42) } }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(reply(valid)).mockResolvedValueOnce(reply(invalid)))
    await expect(fetchSupervisorReview(7)).resolves.toMatchObject({ inquiry_id: 7 })
    await expect(fetchSupervisorReview(7)).rejects.toThrow('Invalid response body')
  })
})