import { requestJson } from './client'

// Mirrors AnalysisView in backend/app/parsing/service.py, ParsedFields in
// backend/app/parsing/schema.py, RunSummary in backend/app/tracing/summary.py and
// ChecksView / CheckResults in backend/app/checks/{service,schema}.py and OrchestrationView /
// OrchestrationResult in backend/app/orchestration/{service,schema}.py and RecommendationView /
// RecommendationResult in backend/app/recommendation/{service,schema}.py and PolicyView /
// PolicyResult in backend/app/policy/{service,schema}.py and DraftView / DecisionView /
// DraftOffer in backend/app/draft/{service,schema}.py (prefixed ReplyDraft here: the analysis
// form already has its own Draft).
// Decimal values (price_value, cost_usd, amounts and percents of the checks, the
// recommendation, the policy and the reply draft) arrive as JSON strings.

export type FieldName =
  | 'customer'
  | 'product_code'
  | 'quantity'
  | 'deadline'
  | 'substitute_allowed'
  | 'price'

export type PriceKind = 'none' | 'best_price' | 'discount_percent' | 'target_price'

export type Extractor = 'fake' | 'groq' | 'openrouter'

export type ParsedFields = {
  customer: string | null
  product_code: string | null
  quantity: number | null
  deadline: string | null // ISO date
  deadline_text: string | null // phrase as written
  substitute_allowed: boolean | null
  price_kind: PriceKind
  price_value: string | null // percent for discount_percent, amount for target_price
  price_text: string | null // phrase as written
}

export type PriceStatus = 'priced' | 'unpriced' | 'not_applicable'

export type StepSummary = {
  id: number
  name: string
  kind: 'deterministic' | 'llm'
  status: 'ok' | 'failed'
  error_type: string | null
  provider: string | null
  model: string | null
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  cost_usd: string | null
  price_status: PriceStatus
  price_source: string | null
  started_at: string
  duration_ms: number
}

export type RunTotals = {
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cost_usd: string // sum over priced steps only
  cost_complete: boolean // false when any step is unpriced
  steps_duration_ms: number
  duration_ms: number | null
}

export type RunSummary = {
  id: number
  status: 'running' | 'completed' | 'failed'
  started_at: string
  duration_ms: number | null
  steps: StepSummary[]
  totals: RunTotals
}

export type Outcome = 'standard' | 'exception' | 'needs_input'

export type ExceptionType = 'insufficient_stock'

export type NeedsInputReason =
  | 'customer_missing'
  | 'customer_not_found'
  | 'customer_ambiguous'
  | 'product_missing'
  | 'product_not_found'
  | 'quantity_missing'

// Analysis fields the checks depend on.
export type CheckInput = 'customer' | 'product_code' | 'quantity'

export type CustomerCheck = {
  status: 'matched' | 'missing' | 'not_found' | 'ambiguous'
  matched_by: 'name' | 'email' | null
  customer_id: number | null
  name: string | null
  candidates: string[] // names when ambiguous
}

export type StockCheck = {
  status: 'ok' | 'insufficient' | 'skipped'
  product_code: string | null // catalogue code when found, else as requested
  product_name: string | null
  requested: number | null
  available: number | null
  shortage: number | null
}

export type PriceCheck = {
  status: 'ok' | 'skipped'
  list_price: string | null
  discount_percent: string | null // the customer's standard discount
  unit_price: string | null
  total: string | null // null without a quantity
  currency: 'PLN'
}

export type DiscountCheck = {
  status: 'ok' | 'above_standard' | 'skipped'
  standard_percent: string | null
  requested_kind: PriceKind
  requested_value: string | null
}

export type CreditCheck = {
  status: 'ok' | 'over_limit' | 'blocked' | 'skipped'
  limit: string | null
  balance: string | null
  order_value: string | null
}

export type CheckResults = {
  customer: CustomerCheck
  stock: StockCheck
  price: PriceCheck
  discount: DiscountCheck
  credit: CreditCheck
  reasons: NeedsInputReason[]
}

export type ChecksView = {
  outcome: Outcome
  exception_type: ExceptionType | null
  reasons: NeedsInputReason[]
  results: CheckResults
  checked_at: string
  stale: boolean // computed from an analysis version that is no longer current
  uncertain_inputs: CheckInput[] // uncertain analysis fields the checks used
  run: RunSummary | null // null when the run could not be traced
}

export type Capability =
  | 'substitute-compatibility'
  | 'substitute-availability'
  | 'supplier-availability'
  | 'customer-history'

// From the analysis' substitute_allowed: true / false / null.
export type SubstituteConsent = 'confirmed' | 'refused' | 'unconfirmed'

export type OrchestrationStatus = 'completed' | 'partial' | 'failed'

export type TaskStatus = 'completed' | 'failed' | 'skipped'

export type Compatibility = 'full' | 'partial'

export type HistorySignal =
  | 'accepted_before'
  | 'declined_before'
  | 'mixed'
  | 'no_substitute_history'

export type OrchestrationErrorKind = 'planner_failed' | 'plan_rejected' | 'capability_mismatch'

export type PlannedTask = {
  capability: Capability
  reason: string
}

// The planner's raw answer, kept also when the plan was rejected.
export type PlannerChoice = {
  tasks: PlannedTask[]
  summary: string
}

export type SubstituteCandidate = {
  code: string
  name: string
  compatibility: Compatibility
  note: string
}

export type SubstituteCompatibilityResult = {
  capability: 'substitute-compatibility'
  candidates: SubstituteCandidate[]
}

export type SubstituteStock = {
  code: string
  stock: number
  covers_shortage: boolean
}

export type SubstituteAvailabilityResult = {
  capability: 'substitute-availability'
  candidates: SubstituteStock[]
}

export type SupplierDelivery = {
  supplier: string
  quantity: number
  lead_time_days: number
  available_on: string // ISO date
  meets_deadline: boolean | null // null when the inquiry has no deadline
  covers_shortage: boolean
}

export type SupplierAvailabilityResult = {
  capability: 'supplier-availability'
  offers: SupplierDelivery[]
}

export type CustomerHistoryResult = {
  capability: 'customer-history'
  orders_count: number
  substitutes_offered: number
  substitutes_accepted: number
  signal: HistorySignal
}

// Told apart by `capability`.
export type AgentResult =
  | SubstituteCompatibilityResult
  | SubstituteAvailabilityResult
  | SupplierAvailabilityResult
  | CustomerHistoryResult

export type TaskOutcome = {
  capability: Capability
  agent: string
  reason: string // the planner's reason
  depends_on: Capability[]
  stage: number // 1-based
  status: TaskStatus
  steps: string[] // trace step names, one per attempt; empty when skipped
  error_type: string | null // exception class name only
  result: AgentResult | null
}

export type OrchestrationError = {
  kind: OrchestrationErrorKind
  code: string // e.g. substitute_refused, missing_prerequisite, no_agent, rate_limited
  message: string
}

export type OrchestrationView = {
  status: OrchestrationStatus
  consent: SubstituteConsent
  planner: string // planner name, e.g. fake, groq
  planner_choice: PlannerChoice | null // kept also when the plan was rejected
  planner_steps: string[]
  tasks: TaskOutcome[]
  error: OrchestrationError | null
  orchestrated_at: string
  stale: boolean // computed from an analysis version that is no longer current
  run: RunSummary | null // null when the run could not be traced
}

export type OptionKind = 'partial_delivery' | 'substitute' | 'other_source' | 'combined'

export type LineSource = 'stock' | 'substitute_stock' | 'supplier'

export type SignalPolarity = 'positive' | 'risk' | 'info'

export type ConfidenceBand = 'HIGH' | 'MEDIUM' | 'LOW'

export type RecommendationStatus = 'completed' | 'failed'

export type RecommendationErrorKind = 'recommender_failed' | 'choice_rejected'

// One source of an option: a product, a quantity, where it comes from and when.
export type OptionLine = {
  product_code: string
  product_name: string
  source: LineSource
  supplier: string | null // only for supplier lines
  quantity: number
  available_on: string // ISO date
  unit_price: string // list price of the offered product less the customer's discount
  unit_cost: string
  value: string
  cost: string
}

export type Signal = {
  code: string // e.g. full_coverage, task_failed:customer-history
  polarity: SignalPolarity
  label: string // Polish text from the backend
}

export type RecommendationOption = {
  id: string // e.g. stock+ABC-110, stock+supplier:Hydro-Valve
  kind: OptionKind
  lines: OptionLine[]
  covered_quantity: number
  requested_quantity: number
  fulfilled_on: string // ISO date, the latest date of the lines
  meets_deadline: boolean | null // null when the inquiry has no deadline
  value: string
  cost: string
  margin_percent: string
  band: ConfidenceBand
  signals: Signal[]
}

// The recommender's raw answer, kept also when the choice was rejected.
export type RecommenderChoice = {
  option_id: string
  justification: string
  cited_signals: string[] // signal codes of the chosen option
}

export type RecommendationError = {
  kind: RecommendationErrorKind
  code: string // e.g. unknown_option, foreign_signal, rate_limited
  message: string
}

export type RecommendationView = {
  recommender: string // recommender name, e.g. rule-based, groq
  options: RecommendationOption[] // in build order
  choice: RecommenderChoice | null
  choice_steps: string[] // trace step names, one per attempt
  error: RecommendationError | null
  status: RecommendationStatus
  recommended_at: string
  stale: boolean // computed from an analysis, check result or orchestration no longer current
  run: RunSummary | null // null when the run could not be traced
}

export type RuleCode = 'margin' | 'discount' | 'order_value' | 'credit'

export type RuleVerdict = 'pass' | 'fail' | 'not_evaluated'

export type PolicyOutcome = 'no_approval_needed' | 'requires_supervisor'

export type RuleUnit = 'percent' | 'PLN'

// One rule: the actual value next to its threshold, the verdict and a short English reason.
export type RuleResult = {
  code: RuleCode
  verdict: RuleVerdict
  actual: string | null
  threshold: string | null
  unit: RuleUnit
  reason: string
}

export type PolicyView = {
  option_id: string // the recommended option the rules were evaluated on
  rules: RuleResult[] // always margin, discount, order_value, credit
  outcome: PolicyOutcome
  thresholds_are_examples: boolean
  evaluated_at: string
  stale: boolean // computed from a recommendation that is no longer current
  run: RunSummary | null // null when the run could not be traced
}

// The policy verdict without its stage metadata, as the reply draft carries it.
export type PolicyResult = {
  option_id: string
  rules: RuleResult[]
  outcome: PolicyOutcome
  thresholds_are_examples: boolean
}

export type ReplyDraftStatus = 'draft' | 'ready_to_send' | 'awaiting_supervisor' | 'rejected'

export type ReplyDraftAction = 'edit' | 'approve' | 'reject'

export type ReplyDraftTextSource = 'model' | 'fallback'

// One line of the offer: an option line with the list price of its product.
export type ReplyDraftOfferLine = {
  product_code: string
  product_name: string
  source: LineSource
  supplier: string | null // only for supplier lines
  quantity: number
  available_on: string // ISO date
  list_price: string // catalogue price of the line's product
  unit_price: string // PLN net, offered to the customer
  unit_cost: string
  value: string
  cost: string
}

// The chosen option as recommended, or its edit.
export type ReplyDraftOffer = {
  option_id: string
  kind: OptionKind
  lines: ReplyDraftOfferLine[]
  covered_quantity: number
  requested_quantity: number
  fulfilled_on: string // ISO date
  meets_deadline: boolean | null // null when the inquiry has no deadline
  value: string
  cost: string
  margin_percent: string
  edited: boolean
}

// "Why this recommendation?": the justification and the Polish labels of the cited signals.
export type ReplyDraftWhy = {
  justification: string
  signals: string[]
}

export type ReplyDraftView = {
  status: ReplyDraftStatus
  offer: ReplyDraftOffer
  subject: string
  body: string // the e-mail in Polish, rendered by the backend from the offer
  text_source: ReplyDraftTextSource // fallback: the model's paragraphs were unavailable
  why: ReplyDraftWhy | null // null when the stored recommendation has no chosen option
  // The verdict in force: the edit's own for an edited offer, the policy stage's otherwise.
  policy: PolicyResult | null
  // built from another recommendation, the recommendation is not current, or (offer as
  // recommended) the policy stage's verdict is missing or stale
  stale: boolean
  drafted_at: string
  updated_at: string // sent back unchanged with an edit or a decision
  run: RunSummary | null // null when the run could not be traced
}

// What a decision was about: the offer and the verdict in force at that time.
export type ReplyDraftSnapshot = {
  offer: ReplyDraftOffer
  policy_outcome: PolicyOutcome | null
  failing_rules: RuleCode[]
}

export type ReplyDraftDecision = {
  action: ReplyDraftAction
  status_after: ReplyDraftStatus
  reason: string | null
  decided_by_name: string | null
  decided_at: string
  snapshot: ReplyDraftSnapshot
  current: boolean // made on a draft of the current recommendation
}

export type ReplyDraftLineEdit = {
  product_code: string
  quantity: number
  unit_price: string // decimal, at most two places
}

export type ReplyDraftEdit = {
  option_id: string
  lines: ReplyDraftLineEdit[] // exactly the option's lines, in its order
  reason: string
}

export type Analysis = {
  inquiry_id: number
  extractor: Extractor
  reference_date: string
  fields: ParsedFields
  model_fields: ParsedFields // values as the model (or rule-based parser) returned them
  uncertain: Partial<Record<FieldName, string>> // field → reason
  corrected_fields: FieldName[] // fields whose value differs from the model's
  analyzed_at: string
  analyzed_by_name: string | null
  corrected_at: string | null
  corrected_by_name: string | null
  run: RunSummary | null // null when the run could not be traced
  checks: ChecksView | null // null until the checks succeeded once; has its own run
  orchestration: OrchestrationView | null // null until an exception was orchestrated; own run
  // null without a recommendation; has its own run. Optional: older payloads lack it.
  recommendation?: RecommendationView | null
  // null without a policy verdict; has its own run. Optional: older payloads lack it.
  policy?: PolicyView | null
  // null without a reply draft; has its own run. Optional: older payloads lack it.
  draft?: ReplyDraftView | null
  // every decision on the inquiry's drafts, oldest first. Optional: older payloads lack it.
  decisions?: ReplyDraftDecision[]
}

export const FIELD_NAMES: readonly FieldName[] = [
  'customer',
  'product_code',
  'quantity',
  'deadline',
  'substitute_allowed',
  'price',
]

const PRICE_KINDS: readonly PriceKind[] = ['none', 'best_price', 'discount_percent', 'target_price']

const OUTCOMES: readonly Outcome[] = ['standard', 'exception', 'needs_input']

const NEEDS_INPUT_REASONS: readonly NeedsInputReason[] = [
  'customer_missing',
  'customer_not_found',
  'customer_ambiguous',
  'product_missing',
  'product_not_found',
  'quantity_missing',
]

const CHECK_INPUTS: readonly CheckInput[] = ['customer', 'product_code', 'quantity']

const CAPABILITIES: readonly Capability[] = [
  'substitute-compatibility',
  'substitute-availability',
  'supplier-availability',
  'customer-history',
]

const CONSENTS: readonly SubstituteConsent[] = ['confirmed', 'refused', 'unconfirmed']

const ORCHESTRATION_STATUSES: readonly OrchestrationStatus[] = ['completed', 'partial', 'failed']

const TASK_STATUSES: readonly TaskStatus[] = ['completed', 'failed', 'skipped']

const HISTORY_SIGNALS: readonly HistorySignal[] = [
  'accepted_before',
  'declined_before',
  'mixed',
  'no_substitute_history',
]

const ERROR_KINDS: readonly OrchestrationErrorKind[] = [
  'planner_failed',
  'plan_rejected',
  'capability_mismatch',
]

const OPTION_KINDS: readonly OptionKind[] = [
  'partial_delivery',
  'substitute',
  'other_source',
  'combined',
]

const LINE_SOURCES: readonly LineSource[] = ['stock', 'substitute_stock', 'supplier']

const POLARITIES: readonly SignalPolarity[] = ['positive', 'risk', 'info']

const BANDS: readonly ConfidenceBand[] = ['HIGH', 'MEDIUM', 'LOW']

const RECOMMENDATION_STATUSES: readonly RecommendationStatus[] = ['completed', 'failed']

const RECOMMENDATION_ERROR_KINDS: readonly RecommendationErrorKind[] = [
  'recommender_failed',
  'choice_rejected',
]

const RULE_CODES: readonly RuleCode[] = ['margin', 'discount', 'order_value', 'credit']

const RULE_VERDICTS: readonly RuleVerdict[] = ['pass', 'fail', 'not_evaluated']

const POLICY_OUTCOMES: readonly PolicyOutcome[] = ['no_approval_needed', 'requires_supervisor']

const RULE_UNITS: readonly RuleUnit[] = ['percent', 'PLN']

const REPLY_DRAFT_STATUSES: readonly ReplyDraftStatus[] = [
  'draft',
  'ready_to_send',
  'awaiting_supervisor',
  'rejected',
]

const REPLY_DRAFT_ACTIONS: readonly ReplyDraftAction[] = ['edit', 'approve', 'reject']

const TEXT_SOURCES: readonly ReplyDraftTextSource[] = ['model', 'fallback']

// The 409 detail of an edit or a decision made on a draft that was written meanwhile.
export const DRAFT_CHANGED = 'Draft changed, reload'

type Json = Record<string, unknown>

function isObject(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringOrNull(value: unknown): value is string | null {
  return typeof value === 'string' || value === null
}

function isNumberOrNull(value: unknown): value is number | null {
  return typeof value === 'number' || value === null
}

function isOneOf<T>(value: unknown, options: readonly T[]): value is T {
  return options.includes(value as T)
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

export function isOutcome(value: unknown): value is Outcome {
  return isOneOf(value, OUTCOMES)
}

function isNeedsInputReasons(value: unknown): value is NeedsInputReason[] {
  return Array.isArray(value) && value.every((item) => isOneOf(item, NEEDS_INPUT_REASONS))
}

function isFieldName(value: unknown): value is FieldName {
  return FIELD_NAMES.includes(value as FieldName)
}

function isParsedFields(value: unknown): value is ParsedFields {
  if (!isObject(value)) return false
  return (
    isStringOrNull(value.customer) &&
    isStringOrNull(value.product_code) &&
    isNumberOrNull(value.quantity) &&
    isStringOrNull(value.deadline) &&
    isStringOrNull(value.deadline_text) &&
    (typeof value.substitute_allowed === 'boolean' || value.substitute_allowed === null) &&
    PRICE_KINDS.includes(value.price_kind as PriceKind) &&
    isStringOrNull(value.price_value) &&
    isStringOrNull(value.price_text)
  )
}

function isStepSummary(value: unknown): value is StepSummary {
  if (!isObject(value)) return false
  return (
    typeof value.id === 'number' &&
    typeof value.name === 'string' &&
    (value.kind === 'deterministic' || value.kind === 'llm') &&
    (value.status === 'ok' || value.status === 'failed') &&
    isStringOrNull(value.error_type) &&
    isStringOrNull(value.provider) &&
    isStringOrNull(value.model) &&
    typeof value.input_tokens === 'number' &&
    typeof value.output_tokens === 'number' &&
    isStringOrNull(value.cost_usd) &&
    (value.price_status === 'priced' ||
      value.price_status === 'unpriced' ||
      value.price_status === 'not_applicable') &&
    typeof value.duration_ms === 'number'
  )
}

function isRunTotals(value: unknown): value is RunTotals {
  if (!isObject(value)) return false
  return (
    typeof value.input_tokens === 'number' &&
    typeof value.output_tokens === 'number' &&
    typeof value.cost_usd === 'string' &&
    typeof value.cost_complete === 'boolean' &&
    typeof value.steps_duration_ms === 'number' &&
    isNumberOrNull(value.duration_ms)
  )
}

function isRunSummary(value: unknown): value is RunSummary {
  if (!isObject(value)) return false
  return (
    typeof value.id === 'number' &&
    typeof value.status === 'string' &&
    isNumberOrNull(value.duration_ms) &&
    Array.isArray(value.steps) &&
    value.steps.every(isStepSummary) &&
    isRunTotals(value.totals)
  )
}

function isUncertain(value: unknown): value is Partial<Record<FieldName, string>> {
  return (
    isObject(value) &&
    Object.entries(value).every(([key, reason]) => isFieldName(key) && typeof reason === 'string')
  )
}

function isCustomerCheck(value: unknown): value is CustomerCheck {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, ['matched', 'missing', 'not_found', 'ambiguous']) &&
    (value.matched_by === 'name' || value.matched_by === 'email' || value.matched_by === null) &&
    isNumberOrNull(value.customer_id) &&
    isStringOrNull(value.name) &&
    isStringList(value.candidates)
  )
}

function isStockCheck(value: unknown): value is StockCheck {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, ['ok', 'insufficient', 'skipped']) &&
    isStringOrNull(value.product_code) &&
    isStringOrNull(value.product_name) &&
    isNumberOrNull(value.requested) &&
    isNumberOrNull(value.available) &&
    isNumberOrNull(value.shortage)
  )
}

function isPriceCheck(value: unknown): value is PriceCheck {
  if (!isObject(value)) return false
  return (
    (value.status === 'ok' || value.status === 'skipped') &&
    isStringOrNull(value.list_price) &&
    isStringOrNull(value.discount_percent) &&
    isStringOrNull(value.unit_price) &&
    isStringOrNull(value.total) &&
    value.currency === 'PLN'
  )
}

function isDiscountCheck(value: unknown): value is DiscountCheck {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, ['ok', 'above_standard', 'skipped']) &&
    isStringOrNull(value.standard_percent) &&
    isOneOf(value.requested_kind, PRICE_KINDS) &&
    isStringOrNull(value.requested_value)
  )
}

function isCreditCheck(value: unknown): value is CreditCheck {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, ['ok', 'over_limit', 'blocked', 'skipped']) &&
    isStringOrNull(value.limit) &&
    isStringOrNull(value.balance) &&
    isStringOrNull(value.order_value)
  )
}

function isCheckResults(value: unknown): value is CheckResults {
  if (!isObject(value)) return false
  return (
    isCustomerCheck(value.customer) &&
    isStockCheck(value.stock) &&
    isPriceCheck(value.price) &&
    isDiscountCheck(value.discount) &&
    isCreditCheck(value.credit) &&
    isNeedsInputReasons(value.reasons)
  )
}

function isChecksView(value: unknown): value is ChecksView {
  if (!isObject(value)) return false
  return (
    isOutcome(value.outcome) &&
    (value.exception_type === 'insufficient_stock' || value.exception_type === null) &&
    isNeedsInputReasons(value.reasons) &&
    isCheckResults(value.results) &&
    typeof value.checked_at === 'string' &&
    typeof value.stale === 'boolean' &&
    Array.isArray(value.uncertain_inputs) &&
    value.uncertain_inputs.every((item) => isOneOf(item, CHECK_INPUTS)) &&
    (value.run === null || isRunSummary(value.run))
  )
}

function isCapability(value: unknown): value is Capability {
  return isOneOf(value, CAPABILITIES)
}

function isPlannerChoice(value: unknown): value is PlannerChoice {
  if (!isObject(value)) return false
  return (
    Array.isArray(value.tasks) &&
    value.tasks.every(
      (task) => isObject(task) && isCapability(task.capability) && typeof task.reason === 'string',
    ) &&
    typeof value.summary === 'string'
  )
}

function isSubstituteCandidate(value: unknown): value is SubstituteCandidate {
  if (!isObject(value)) return false
  return (
    typeof value.code === 'string' &&
    typeof value.name === 'string' &&
    (value.compatibility === 'full' || value.compatibility === 'partial') &&
    typeof value.note === 'string'
  )
}

function isSubstituteStock(value: unknown): value is SubstituteStock {
  if (!isObject(value)) return false
  return (
    typeof value.code === 'string' &&
    typeof value.stock === 'number' &&
    typeof value.covers_shortage === 'boolean'
  )
}

function isSupplierDelivery(value: unknown): value is SupplierDelivery {
  if (!isObject(value)) return false
  return (
    typeof value.supplier === 'string' &&
    typeof value.quantity === 'number' &&
    typeof value.lead_time_days === 'number' &&
    typeof value.available_on === 'string' &&
    (typeof value.meets_deadline === 'boolean' || value.meets_deadline === null) &&
    typeof value.covers_shortage === 'boolean'
  )
}

// Told apart by `capability`, like the discriminated union of the backend.
function isAgentResult(value: unknown): value is AgentResult {
  if (!isObject(value)) return false
  switch (value.capability) {
    case 'substitute-compatibility':
      return Array.isArray(value.candidates) && value.candidates.every(isSubstituteCandidate)
    case 'substitute-availability':
      return Array.isArray(value.candidates) && value.candidates.every(isSubstituteStock)
    case 'supplier-availability':
      return Array.isArray(value.offers) && value.offers.every(isSupplierDelivery)
    case 'customer-history':
      return (
        typeof value.orders_count === 'number' &&
        typeof value.substitutes_offered === 'number' &&
        typeof value.substitutes_accepted === 'number' &&
        isOneOf(value.signal, HISTORY_SIGNALS)
      )
    default:
      return false
  }
}

function isTaskOutcome(value: unknown): value is TaskOutcome {
  if (!isObject(value)) return false
  return (
    isCapability(value.capability) &&
    typeof value.agent === 'string' &&
    typeof value.reason === 'string' &&
    Array.isArray(value.depends_on) &&
    value.depends_on.every(isCapability) &&
    typeof value.stage === 'number' &&
    isOneOf(value.status, TASK_STATUSES) &&
    isStringList(value.steps) &&
    isStringOrNull(value.error_type) &&
    (value.result === null || isAgentResult(value.result))
  )
}

function isOrchestrationError(value: unknown): value is OrchestrationError {
  if (!isObject(value)) return false
  return (
    isOneOf(value.kind, ERROR_KINDS) &&
    typeof value.code === 'string' &&
    typeof value.message === 'string'
  )
}

export function isOrchestrationView(value: unknown): value is OrchestrationView {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, ORCHESTRATION_STATUSES) &&
    isOneOf(value.consent, CONSENTS) &&
    typeof value.planner === 'string' &&
    (value.planner_choice === null || isPlannerChoice(value.planner_choice)) &&
    isStringList(value.planner_steps) &&
    Array.isArray(value.tasks) &&
    value.tasks.every(isTaskOutcome) &&
    (value.error === null || isOrchestrationError(value.error)) &&
    typeof value.orchestrated_at === 'string' &&
    typeof value.stale === 'boolean' &&
    (value.run === null || isRunSummary(value.run))
  )
}

function isOptionLine(value: unknown): value is OptionLine {
  if (!isObject(value)) return false
  return (
    typeof value.product_code === 'string' &&
    typeof value.product_name === 'string' &&
    isOneOf(value.source, LINE_SOURCES) &&
    isStringOrNull(value.supplier) &&
    typeof value.quantity === 'number' &&
    typeof value.available_on === 'string' &&
    typeof value.unit_price === 'string' &&
    typeof value.unit_cost === 'string' &&
    typeof value.value === 'string' &&
    typeof value.cost === 'string'
  )
}

function isSignal(value: unknown): value is Signal {
  if (!isObject(value)) return false
  return (
    typeof value.code === 'string' &&
    isOneOf(value.polarity, POLARITIES) &&
    typeof value.label === 'string'
  )
}

function isRecommendationOption(value: unknown): value is RecommendationOption {
  if (!isObject(value)) return false
  return (
    typeof value.id === 'string' &&
    isOneOf(value.kind, OPTION_KINDS) &&
    Array.isArray(value.lines) &&
    value.lines.every(isOptionLine) &&
    typeof value.covered_quantity === 'number' &&
    typeof value.requested_quantity === 'number' &&
    typeof value.fulfilled_on === 'string' &&
    (typeof value.meets_deadline === 'boolean' || value.meets_deadline === null) &&
    typeof value.value === 'string' &&
    typeof value.cost === 'string' &&
    typeof value.margin_percent === 'string' &&
    isOneOf(value.band, BANDS) &&
    Array.isArray(value.signals) &&
    value.signals.every(isSignal)
  )
}

function isRecommenderChoice(value: unknown): value is RecommenderChoice {
  if (!isObject(value)) return false
  return (
    typeof value.option_id === 'string' &&
    typeof value.justification === 'string' &&
    isStringList(value.cited_signals)
  )
}

function isRecommendationError(value: unknown): value is RecommendationError {
  if (!isObject(value)) return false
  return (
    isOneOf(value.kind, RECOMMENDATION_ERROR_KINDS) &&
    typeof value.code === 'string' &&
    typeof value.message === 'string'
  )
}

export function isRecommendationView(value: unknown): value is RecommendationView {
  if (!isObject(value)) return false
  return (
    typeof value.recommender === 'string' &&
    Array.isArray(value.options) &&
    value.options.every(isRecommendationOption) &&
    (value.choice === null || isRecommenderChoice(value.choice)) &&
    isStringList(value.choice_steps) &&
    (value.error === null || isRecommendationError(value.error)) &&
    isOneOf(value.status, RECOMMENDATION_STATUSES) &&
    typeof value.recommended_at === 'string' &&
    typeof value.stale === 'boolean' &&
    (value.run === null || isRunSummary(value.run))
  )
}

function isRuleResult(value: unknown): value is RuleResult {
  if (!isObject(value)) return false
  return (
    isOneOf(value.code, RULE_CODES) &&
    isOneOf(value.verdict, RULE_VERDICTS) &&
    isStringOrNull(value.actual) &&
    isStringOrNull(value.threshold) &&
    isOneOf(value.unit, RULE_UNITS) &&
    typeof value.reason === 'string'
  )
}

export function isPolicyView(value: unknown): value is PolicyView {
  if (!isObject(value)) return false
  return (
    typeof value.option_id === 'string' &&
    Array.isArray(value.rules) &&
    value.rules.every(isRuleResult) &&
    isOneOf(value.outcome, POLICY_OUTCOMES) &&
    typeof value.thresholds_are_examples === 'boolean' &&
    typeof value.evaluated_at === 'string' &&
    typeof value.stale === 'boolean' &&
    (value.run === null || isRunSummary(value.run))
  )
}

function isPolicyResult(value: unknown): value is PolicyResult {
  if (!isObject(value)) return false
  return (
    typeof value.option_id === 'string' &&
    Array.isArray(value.rules) &&
    value.rules.every(isRuleResult) &&
    isOneOf(value.outcome, POLICY_OUTCOMES) &&
    typeof value.thresholds_are_examples === 'boolean'
  )
}

function isReplyDraftOfferLine(value: unknown): value is ReplyDraftOfferLine {
  if (!isObject(value)) return false
  return (
    typeof value.product_code === 'string' &&
    typeof value.product_name === 'string' &&
    isOneOf(value.source, LINE_SOURCES) &&
    isStringOrNull(value.supplier) &&
    typeof value.quantity === 'number' &&
    typeof value.available_on === 'string' &&
    typeof value.list_price === 'string' &&
    typeof value.unit_price === 'string' &&
    typeof value.unit_cost === 'string' &&
    typeof value.value === 'string' &&
    typeof value.cost === 'string'
  )
}

function isReplyDraftOffer(value: unknown): value is ReplyDraftOffer {
  if (!isObject(value)) return false
  return (
    typeof value.option_id === 'string' &&
    isOneOf(value.kind, OPTION_KINDS) &&
    Array.isArray(value.lines) &&
    value.lines.every(isReplyDraftOfferLine) &&
    typeof value.covered_quantity === 'number' &&
    typeof value.requested_quantity === 'number' &&
    typeof value.fulfilled_on === 'string' &&
    (typeof value.meets_deadline === 'boolean' || value.meets_deadline === null) &&
    typeof value.value === 'string' &&
    typeof value.cost === 'string' &&
    typeof value.margin_percent === 'string' &&
    typeof value.edited === 'boolean'
  )
}

function isReplyDraftWhy(value: unknown): value is ReplyDraftWhy {
  if (!isObject(value)) return false
  return typeof value.justification === 'string' && isStringList(value.signals)
}

export function isReplyDraftView(value: unknown): value is ReplyDraftView {
  if (!isObject(value)) return false
  return (
    isOneOf(value.status, REPLY_DRAFT_STATUSES) &&
    isReplyDraftOffer(value.offer) &&
    typeof value.subject === 'string' &&
    typeof value.body === 'string' &&
    isOneOf(value.text_source, TEXT_SOURCES) &&
    (value.why === null || isReplyDraftWhy(value.why)) &&
    (value.policy === null || isPolicyResult(value.policy)) &&
    typeof value.stale === 'boolean' &&
    typeof value.drafted_at === 'string' &&
    typeof value.updated_at === 'string' &&
    (value.run === null || isRunSummary(value.run))
  )
}

function isReplyDraftSnapshot(value: unknown): value is ReplyDraftSnapshot {
  if (!isObject(value)) return false
  return (
    isReplyDraftOffer(value.offer) &&
    (value.policy_outcome === null || isOneOf(value.policy_outcome, POLICY_OUTCOMES)) &&
    Array.isArray(value.failing_rules) &&
    value.failing_rules.every((code) => isOneOf(code, RULE_CODES))
  )
}

export function isReplyDraftDecision(value: unknown): value is ReplyDraftDecision {
  if (!isObject(value)) return false
  return (
    isOneOf(value.action, REPLY_DRAFT_ACTIONS) &&
    isOneOf(value.status_after, REPLY_DRAFT_STATUSES) &&
    isStringOrNull(value.reason) &&
    isStringOrNull(value.decided_by_name) &&
    typeof value.decided_at === 'string' &&
    isReplyDraftSnapshot(value.snapshot) &&
    typeof value.current === 'boolean'
  )
}

function isAnalysis(value: unknown): value is Analysis {
  if (!isObject(value)) return false
  return (
    typeof value.inquiry_id === 'number' &&
    (value.extractor === 'fake' || value.extractor === 'groq' || value.extractor === 'openrouter') &&
    typeof value.reference_date === 'string' &&
    isParsedFields(value.fields) &&
    isParsedFields(value.model_fields) &&
    isUncertain(value.uncertain) &&
    Array.isArray(value.corrected_fields) &&
    value.corrected_fields.every(isFieldName) &&
    typeof value.analyzed_at === 'string' &&
    isStringOrNull(value.analyzed_by_name) &&
    isStringOrNull(value.corrected_at) &&
    isStringOrNull(value.corrected_by_name) &&
    (value.run === null || isRunSummary(value.run)) &&
    (value.checks === null || isChecksView(value.checks)) &&
    (value.orchestration === null || isOrchestrationView(value.orchestration)) &&
    (value.recommendation === undefined ||
      value.recommendation === null ||
      isRecommendationView(value.recommendation)) &&
    (value.policy === undefined || value.policy === null || isPolicyView(value.policy)) &&
    (value.draft === undefined || value.draft === null || isReplyDraftView(value.draft)) &&
    (value.decisions === undefined ||
      (Array.isArray(value.decisions) && value.decisions.every(isReplyDraftDecision)))
  )
}

function isAnalysisOrNull(value: unknown): value is Analysis | null {
  return value === null || isAnalysis(value)
}

function analysisPath(inquiryId: number): string {
  return `/api/inquiries/${inquiryId}/analysis`
}

// GET: the current analysis, or null when the inquiry has not been analyzed yet.
export function fetchAnalysis(inquiryId: number, signal?: AbortSignal): Promise<Analysis | null> {
  return requestJson(analysisPath(inquiryId), isAnalysisOrNull, { signal })
}

// POST: analyze the inquiry, replacing its analysis and corrections. Extraction
// failures are ApiError 502/503 and leave the stored analysis unchanged.
export function analyzeInquiry(inquiryId: number): Promise<Analysis> {
  return requestJson(analysisPath(inquiryId), isAnalysis, { method: 'POST' })
}

// PUT: save the user's values. `analyzedAt` is the analyzed_at of the analysis the
// corrections were made on, sent back unchanged; a replaced analysis is ApiError 409.
export function saveCorrections(
  inquiryId: number,
  fields: ParsedFields,
  reviewed: FieldName[],
  analyzedAt: string,
): Promise<Analysis> {
  return requestJson(analysisPath(inquiryId), isAnalysis, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields, reviewed, analyzed_at: analyzedAt }),
  })
}

// POST: run the checks again in a new run for the current analysis (after a stale or
// missing result). Answers with the whole analysis; without an analysis ApiError 404.
export function rerunChecks(inquiryId: number): Promise<Analysis> {
  return requestJson(`/api/inquiries/${inquiryId}/checks`, isAnalysis, { method: 'POST' })
}

// POST: run only the orchestration again in a new run for the current analysis (after a
// stale, failed or partial result, or none yet). Answers with the whole analysis; without an
// analysis ApiError 404, without a current exception ApiError 409 "Nothing to orchestrate".
export function rerunOrchestration(inquiryId: number): Promise<Analysis> {
  return requestJson(`/api/inquiries/${inquiryId}/orchestration`, isAnalysis, { method: 'POST' })
}

// POST: run only the recommendation again in a new run for the current orchestration (after a
// stale or failed result, or none yet). Answers with the whole analysis; without an analysis
// ApiError 404, without a current exception with a completed or partial orchestration
// ApiError 409 "Nothing to recommend".
export function rerunRecommendation(inquiryId: number): Promise<Analysis> {
  return requestJson(`/api/inquiries/${inquiryId}/recommendation`, isAnalysis, { method: 'POST' })
}

// POST: evaluate the policy again for the current recommendation (after a stale result, or
// none yet). Answers with the whole analysis; without an analysis ApiError 404, without a
// current completed recommendation with a chosen option ApiError 409 "Nothing to evaluate".
export function rerunPolicy(inquiryId: number): Promise<Analysis> {
  return requestJson(`/api/inquiries/${inquiryId}/policy`, isAnalysis, { method: 'POST' })
}

function draftPath(inquiryId: number): string {
  return `/api/inquiries/${inquiryId}/draft`
}

// POST: draft the current recommendation again (the offer as recommended, status draft), when
// there is no draft or it is rejected or stale. Answers with the whole analysis; without a
// current recommendation with a chosen option ApiError 409 "Nothing to draft", for an approved
// draft of the current recommendation ApiError 409 "Draft already decided".
export function regenerateDraft(inquiryId: number): Promise<Analysis> {
  return requestJson(draftPath(inquiryId), isAnalysis, { method: 'POST' })
}

// PUT: edit the draft's offer (another option, quantities and unit prices of its lines) and
// evaluate its policy. `updatedAt` is the updated_at of the draft the edit was made on, sent
// back unchanged; a draft written meanwhile is ApiError 409 DRAFT_CHANGED. A missing reason or
// an invalid edit is ApiError 422.
export function editDraft(
  inquiryId: number,
  updatedAt: string,
  edit: ReplyDraftEdit,
): Promise<Analysis> {
  return requestJson(draftPath(inquiryId), isAnalysis, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updated_at: updatedAt, ...edit }),
  })
}

// POST: approve (optional comment) or reject (reason required) the draft. `updatedAt` as for
// editDraft; a draft written meanwhile is ApiError 409 DRAFT_CHANGED, approving without a
// verdict in force ApiError 409 "Policy verdict missing", rejecting without a reason 422.
export function decideDraft(
  inquiryId: number,
  updatedAt: string,
  action: 'approve' | 'reject',
  reason: string | null,
): Promise<Analysis> {
  return requestJson(`${draftPath(inquiryId)}/decision`, isAnalysis, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updated_at: updatedAt, action, reason }),
  })
}
