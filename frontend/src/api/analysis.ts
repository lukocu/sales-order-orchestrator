import { requestJson } from './client'

// Mirrors AnalysisView in backend/app/parsing/service.py, ParsedFields in
// backend/app/parsing/schema.py and RunSummary in backend/app/tracing/summary.py.
// Decimal values (price_value, cost_usd) arrive as JSON strings.

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
    (value.run === null || isRunSummary(value.run))
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
