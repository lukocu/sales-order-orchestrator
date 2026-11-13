import type {
  PolicyResult,
  PolicyView,
  RecommendationOption,
  ReplyDraftDecision,
  ReplyDraftOffer,
  ReplyDraftView,
  RunSummary,
} from '../api/analysis'
import { ACME_POLICY, DELTA_POLICY } from './policyFixtures'
import { ACME_SUBSTITUTE_OPTION, DELTA_COMBINED_OPTION } from './recommendationFixtures'

// Reply drafts and decisions of the seed inquiries with the fake drafter, the rule-based
// recommender and the example thresholds, as the API returns them.

export function draftRun(): RunSummary {
  return {
    id: 9,
    status: 'completed',
    started_at: '2026-11-10T09:00:06Z',
    duration_ms: 1.2,
    steps: [
      {
        id: 60,
        name: 'draft',
        kind: 'deterministic',
        status: 'ok',
        error_type: null,
        provider: null,
        model: null,
        input_tokens: 0,
        output_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        price_status: 'not_applicable',
        price_source: null,
        started_at: '2026-11-10T09:00:06Z',
        duration_ms: 0.3,
      },
    ],
    totals: {
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cost_usd: '0',
      cost_complete: true,
      steps_duration_ms: 0.3,
      duration_ms: 1.2,
    },
  }
}

// Catalogue prices of the seed products (ABC-100 120.00 PLN, ABC-110 125.00 PLN).
const LIST_PRICES: Record<string, string> = { 'ABC-100': '120.00', 'ABC-110': '125.00' }

function offerOf(option: RecommendationOption): ReplyDraftOffer {
  return {
    option_id: option.id,
    kind: option.kind,
    lines: option.lines.map((line) => ({ ...line, list_price: LIST_PRICES[line.product_code] })),
    covered_quantity: option.covered_quantity,
    requested_quantity: option.requested_quantity,
    fulfilled_on: option.fulfilled_on,
    meets_deadline: option.meets_deadline,
    value: option.value,
    cost: option.cost,
    margin_percent: option.margin_percent,
    edited: false,
  }
}

function verdictOf(view: PolicyView): PolicyResult {
  return {
    option_id: view.option_id,
    rules: view.rules,
    outcome: view.outcome,
    thresholds_are_examples: view.thresholds_are_examples,
  }
}

const INTRO =
  'Dziękujemy za przesłane zapytanie. Nie mamy obecnie na stanie pełnej zamówionej ilości, ' +
  'dlatego przygotowaliśmy propozycję realizacji z udziałem produktu zamiennego o zgodnych ' +
  'parametrach.'

const CLOSING =
  'Proponowany termin realizacji mieści się w oczekiwanym przez Państwa terminie. Prosimy o ' +
  'potwierdzenie propozycji. W razie pytań pozostajemy do dyspozycji.'

export const ACME_OFFER: ReplyDraftOffer = offerOf(ACME_SUBSTITUTE_OPTION)

// ACME: the substitute option as recommended; the policy stage needs no approval.
export const ACME_DRAFT: ReplyDraftView = {
  status: 'draft',
  offer: ACME_OFFER,
  subject: 'Re: Zapytanie ofertowe ABC-100',
  body: [
    'Dzień dobry,',
    '',
    INTRO,
    '',
    'Proponowane pozycje:',
    '- Czujnik ciśnienia ABC-100 (ABC-100): 50 szt. × 114,00 PLN netto = 5 700,00 PLN netto, ' +
      'dostępne od 02.11.2026',
    '- Czujnik ciśnienia ABC-110 (ABC-110): 30 szt. × 118,75 PLN netto = 3 562,50 PLN netto, ' +
      'dostępne od 02.11.2026',
    '',
    'Razem: 9 262,50 PLN netto.',
    'Termin realizacji: 02.11.2026.',
    '',
    CLOSING,
    '',
    'Z poważaniem',
    'Dział sprzedaży',
  ].join('\n'),
  text_source: 'model',
  why: {
    justification:
      'Wybrano opcję stock+ABC-110: pokrycie 80/80 szt., realizacja 2026-11-02, marża 25.51%, ' +
      'pewność HIGH.',
    signals: [
      'Pokrywa całą zamówioną ilość',
      'Realizacja w terminie klienta',
      'Zamiennik ABC-110 w pełni zgodny',
    ],
  },
  policy: verdictOf(ACME_POLICY),
  stale: false,
  drafted_at: '2026-11-10T09:00:06Z',
  updated_at: '2026-11-10T09:00:06.123456Z',
  submitted_by: null,
  run: draftRun(),
}

// ACME with the ABC-100 line cut to 95.00 PLN (20.83% off the list price): the edit's own
// verdict fails the margin and the discount rule.
export const ACME_EDITED_OFFER: ReplyDraftOffer = {
  ...ACME_OFFER,
  lines: [
    { ...ACME_OFFER.lines[0], unit_price: '95.00', value: '4750.00' },
    ACME_OFFER.lines[1],
  ],
  value: '8312.50',
  margin_percent: '16.99',
  edited: true,
}

export const ACME_EDITED_DRAFT: ReplyDraftView = {
  ...ACME_DRAFT,
  offer: ACME_EDITED_OFFER,
  policy: {
    ...verdictOf(ACME_POLICY),
    rules: [
      {
        code: 'margin',
        verdict: 'fail',
        actual: '16.99',
        threshold: '20.00',
        unit: 'percent',
        reason: 'Margin below the minimum',
      },
      {
        code: 'discount',
        verdict: 'fail',
        actual: '20.83',
        threshold: '15.00',
        unit: 'percent',
        reason: 'Offered discount above the maximum',
      },
      ACME_POLICY.rules[2],
      ACME_POLICY.rules[3],
    ],
    outcome: 'requires_supervisor',
  },
  updated_at: '2026-11-10T09:10:00Z',
}

// Hurtownia Delta: the combined option as recommended; the policy stage requires a supervisor.
export const DELTA_DRAFT: ReplyDraftView = {
  ...ACME_DRAFT,
  offer: offerOf(DELTA_COMBINED_OPTION),
  subject: 'Re: Zamówienie ABC-100',
  why: {
    justification: 'Wybrano opcję stock+ABC-110+supplier:Sensortech Polska.',
    signals: ['Pokrywa 290 z 500 szt.'],
  },
  policy: verdictOf(DELTA_POLICY),
}

export const ACME_APPROVED: ReplyDraftDecision = {
  action: 'approve',
  status_after: 'ready_to_send',
  reason: null,
  decided_by_name: 'Anna Kowalska',
  decided_at: '2026-11-10T09:20:00Z',
  snapshot: { offer: ACME_OFFER, policy_outcome: 'no_approval_needed', failing_rules: [] },
  current: true,
}

export const ACME_EDITED: ReplyDraftDecision = {
  action: 'edit',
  status_after: 'draft',
  reason: 'Negocjacje cenowe',
  decided_by_name: 'Anna Kowalska',
  decided_at: '2026-11-10T09:10:00Z',
  snapshot: {
    offer: ACME_EDITED_OFFER,
    policy_outcome: 'requires_supervisor',
    failing_rules: ['margin', 'discount'],
  },
  current: true,
}

export const ACME_REJECTED_EARLIER: ReplyDraftDecision = {
  action: 'reject',
  status_after: 'rejected',
  reason: 'Klient zmienił ilość',
  decided_by_name: 'Anna Kowalska',
  decided_at: '2026-11-10T08:30:00Z',
  snapshot: { offer: ACME_OFFER, policy_outcome: 'no_approval_needed', failing_rules: [] },
  current: false,
}

// Hurtownia Delta passed to the supervisor by the salesperson (user 1) after approving it.
export const DELTA_AWAITING: ReplyDraftView = {
  ...DELTA_DRAFT,
  status: 'awaiting_supervisor',
  updated_at: '2026-11-10T09:30:00Z',
  submitted_by: 1,
}

export const DELTA_SUBMITTED: ReplyDraftDecision = {
  action: 'approve',
  status_after: 'awaiting_supervisor',
  reason: null,
  decided_by_name: 'Anna Kowalska',
  decided_at: '2026-11-10T09:30:00Z',
  snapshot: {
    offer: DELTA_DRAFT.offer,
    policy_outcome: 'requires_supervisor',
    failing_rules: ['margin', 'discount', 'order_value'],
    not_evaluated_rules: [],
  },
  current: true,
}

export const DELTA_SUPERVISOR_REJECTED: ReplyDraftDecision = {
  action: 'supervisor_reject',
  status_after: 'rejected',
  reason: 'Marża za niska',
  decided_by_name: 'Piotr Nowak',
  decided_at: '2026-11-10T09:40:00Z',
  snapshot: {
    offer: DELTA_DRAFT.offer,
    policy_outcome: 'requires_supervisor',
    failing_rules: ['margin', 'discount'],
    not_evaluated_rules: ['credit'],
  },
  current: true,
}
