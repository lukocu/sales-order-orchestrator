import type {
  OptionLine,
  RecommendationOption,
  RecommendationView,
  RunSummary,
  StepSummary,
} from '../api/analysis'

// Recommendations of the seed inquiries with the rule-based recommender, as the API returns
// them (seed prices and costs, the customers' standard discounts).

function step(id: number, name: string, durationMs: number): StepSummary {
  return {
    id,
    name,
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
    started_at: '2026-11-10T09:00:04Z',
    duration_ms: durationMs,
  }
}

export function recommendationRun(stepNames: string[] = ['options', 'choose']): RunSummary {
  const steps = stepNames.map((name, index) => step(40 + index, name, 0.5))
  const sum = steps.reduce((total, item) => total + item.duration_ms, 0)
  return {
    id: 6,
    status: 'completed',
    started_at: '2026-11-10T09:00:04Z',
    duration_ms: 2.5,
    steps,
    totals: {
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cost_usd: '0',
      cost_complete: true,
      steps_duration_ms: sum,
      duration_ms: 2.5,
    },
  }
}

function line(fields: Partial<OptionLine> & Pick<OptionLine, 'quantity'>): OptionLine {
  return {
    product_code: 'ABC-100',
    product_name: 'Czujnik ciśnienia ABC-100',
    source: 'stock',
    supplier: null,
    available_on: '2026-11-02',
    unit_price: '114.00',
    unit_cost: '84.00',
    value: '0.00',
    cost: '0.00',
    ...fields,
  }
}

// ACME, 80 × ABC-100 by 2026-11-06 with 50 in stock, substitute allowed, 5% discount.
const ACME_STOCK_LINE = line({ quantity: 50, value: '5700.00', cost: '4200.00' })

export const ACME_STOCK_OPTION: RecommendationOption = {
  id: 'stock',
  kind: 'partial_delivery',
  lines: [ACME_STOCK_LINE],
  covered_quantity: 50,
  requested_quantity: 80,
  fulfilled_on: '2026-11-02',
  meets_deadline: true,
  value: '5700.00',
  cost: '4200.00',
  margin_percent: '26.32',
  band: 'LOW',
  signals: [
    { code: 'incomplete_coverage', polarity: 'risk', label: 'Pokrywa 50 z 80 szt.' },
    { code: 'deadline_met', polarity: 'positive', label: 'Realizacja w terminie klienta' },
  ],
}

export const ACME_SUBSTITUTE_OPTION: RecommendationOption = {
  id: 'stock+ABC-110',
  kind: 'substitute',
  lines: [
    ACME_STOCK_LINE,
    line({
      product_code: 'ABC-110',
      product_name: 'Czujnik ciśnienia ABC-110',
      source: 'substitute_stock',
      quantity: 30,
      unit_price: '118.75',
      unit_cost: '90.00',
      value: '3562.50',
      cost: '2700.00',
    }),
  ],
  covered_quantity: 80,
  requested_quantity: 80,
  fulfilled_on: '2026-11-02',
  meets_deadline: true,
  value: '9262.50',
  cost: '6900.00',
  margin_percent: '25.51',
  band: 'HIGH',
  signals: [
    { code: 'full_coverage', polarity: 'positive', label: 'Pokrywa całą zamówioną ilość' },
    { code: 'deadline_met', polarity: 'positive', label: 'Realizacja w terminie klienta' },
    { code: 'compat_full', polarity: 'positive', label: 'Zamiennik ABC-110 w pełni zgodny' },
    {
      code: 'consent_confirmed',
      polarity: 'positive',
      label: 'Klient zgodził się na zamiennik',
    },
    {
      code: 'history_accepted',
      polarity: 'positive',
      label: 'Klient przyjmował już zamienniki',
    },
  ],
}

export const ACME_SUPPLIER_OPTION: RecommendationOption = {
  id: 'stock+supplier:Sensortech Polska',
  kind: 'other_source',
  lines: [
    ACME_STOCK_LINE,
    line({
      source: 'supplier',
      supplier: 'Sensortech Polska',
      quantity: 30,
      available_on: '2026-11-09',
      unit_cost: '96.00',
      value: '3420.00',
      cost: '2880.00',
    }),
  ],
  covered_quantity: 80,
  requested_quantity: 80,
  fulfilled_on: '2026-11-09',
  meets_deadline: false,
  value: '9120.00',
  cost: '7080.00',
  margin_percent: '22.37',
  band: 'LOW',
  signals: [
    { code: 'full_coverage', polarity: 'positive', label: 'Pokrywa całą zamówioną ilość' },
    {
      code: 'deadline_missed',
      polarity: 'risk',
      label: 'Realizacja 2026-11-09 po terminie 2026-11-06',
    },
  ],
}

export const ACME_RECOMMENDATION: RecommendationView = {
  recommender: 'rule-based',
  options: [ACME_STOCK_OPTION, ACME_SUBSTITUTE_OPTION, ACME_SUPPLIER_OPTION],
  choice: {
    option_id: 'stock+ABC-110',
    justification:
      'Wybrano opcję stock+ABC-110: pokrycie 80/80 szt., realizacja 2026-11-02, marża ' +
      '25.51%, pewność HIGH. Za: Pokrywa całą zamówioną ilość; Realizacja w terminie ' +
      'klienta; Zamiennik ABC-110 w pełni zgodny; Klient zgodził się na zamiennik; Klient ' +
      'przyjmował już zamienniki.',
    cited_signals: [
      'full_coverage',
      'deadline_met',
      'compat_full',
      'consent_confirmed',
      'history_accepted',
    ],
  },
  choice_steps: ['choose'],
  error: null,
  status: 'completed',
  recommended_at: '2026-11-10T09:00:04Z',
  stale: false,
  run: recommendationRun(),
}

// Hurtownia Delta, 500 × ABC-100 without a deadline with 50 in stock, substitute not stated,
// 10% discount.
const DELTA_STOCK_LINE = line({
  quantity: 50,
  available_on: '2026-11-03',
  unit_price: '108.00',
  value: '5400.00',
  cost: '4200.00',
})

export const DELTA_STOCK_OPTION: RecommendationOption = {
  id: 'stock',
  kind: 'partial_delivery',
  lines: [DELTA_STOCK_LINE],
  covered_quantity: 50,
  requested_quantity: 500,
  fulfilled_on: '2026-11-03',
  meets_deadline: null,
  value: '5400.00',
  cost: '4200.00',
  margin_percent: '22.22',
  band: 'LOW',
  signals: [
    { code: 'incomplete_coverage', polarity: 'risk', label: 'Pokrywa 50 z 500 szt.' },
    { code: 'no_deadline', polarity: 'info', label: 'Zapytanie bez terminu' },
  ],
}

export const DELTA_COMBINED_OPTION: RecommendationOption = {
  id: 'stock+ABC-110+supplier:Sensortech Polska',
  kind: 'combined',
  lines: [
    DELTA_STOCK_LINE,
    line({
      product_code: 'ABC-110',
      product_name: 'Czujnik ciśnienia ABC-110',
      source: 'substitute_stock',
      quantity: 40,
      available_on: '2026-11-03',
      unit_price: '112.50',
      unit_cost: '90.00',
      value: '4500.00',
      cost: '3600.00',
    }),
    line({
      source: 'supplier',
      supplier: 'Sensortech Polska',
      quantity: 200,
      available_on: '2026-11-10',
      unit_price: '108.00',
      unit_cost: '96.00',
      value: '21600.00',
      cost: '19200.00',
    }),
  ],
  covered_quantity: 290,
  requested_quantity: 500,
  fulfilled_on: '2026-11-10',
  meets_deadline: null,
  value: '31500.00',
  cost: '27000.00',
  margin_percent: '14.29',
  band: 'LOW',
  signals: [
    { code: 'incomplete_coverage', polarity: 'risk', label: 'Pokrywa 290 z 500 szt.' },
    { code: 'no_deadline', polarity: 'info', label: 'Zapytanie bez terminu' },
    { code: 'compat_full', polarity: 'positive', label: 'Zamiennik ABC-110 w pełni zgodny' },
    {
      code: 'consent_unconfirmed',
      polarity: 'risk',
      label: 'Brak potwierdzenia zgody na zamiennik',
    },
    { code: 'history_none', polarity: 'info', label: 'Klient nie dostawał dotąd zamienników' },
    {
      code: 'two_sources',
      polarity: 'risk',
      label: 'Brak uzupełniany z dwóch źródeł: zamiennik i dostawca',
    },
  ],
}

export const DELTA_RECOMMENDATION: RecommendationView = {
  recommender: 'rule-based',
  options: [DELTA_STOCK_OPTION, DELTA_COMBINED_OPTION],
  choice: {
    option_id: DELTA_COMBINED_OPTION.id,
    justification:
      'Wybrano opcję stock+ABC-110+supplier:Sensortech Polska: pokrycie 290/500 szt., ' +
      'realizacja 2026-11-10, marża 14.29%, pewność LOW. Za: Zamiennik ABC-110 w pełni ' +
      'zgodny. Ryzyka: Pokrywa 290 z 500 szt.; Brak potwierdzenia zgody na zamiennik; Brak ' +
      'uzupełniany z dwóch źródeł: zamiennik i dostawca.',
    cited_signals: ['incomplete_coverage', 'compat_full', 'consent_unconfirmed', 'two_sources'],
  },
  choice_steps: ['choose'],
  error: null,
  status: 'completed',
  recommended_at: '2026-11-10T09:00:04Z',
  stale: false,
  run: recommendationRun(),
}
