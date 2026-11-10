import { useEffect, useState, type ReactNode } from 'react'
import {
  analyzeInquiry,
  fetchAnalysis,
  saveCorrections,
  type Analysis,
  type FieldName,
  type ParsedFields,
  type PriceKind,
  type RunSummary,
  type StepSummary,
} from '../api/analysis'
import { ApiError, UnauthorizedError } from '../api/client'

type Props = {
  inquiryId: number
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; analysis: Analysis | null }
  | { kind: 'error'; message: string }

type Substitute = 'yes' | 'no' | 'unknown'

// The form keeps what the user typed; it becomes ParsedFields only on save.
type Draft = {
  customer: string
  product_code: string
  quantity: string
  deadline: string
  substitute: Substitute
  price_kind: PriceKind
  price_value: string
}

const DRAFT_KEYS: readonly (keyof Draft)[] = [
  'customer',
  'product_code',
  'quantity',
  'deadline',
  'substitute',
  'price_kind',
  'price_value',
]

const PRICE_KIND_LABEL: Record<PriceKind, string> = {
  none: 'Not stated',
  best_price: 'Best price',
  discount_percent: 'Discount (%)',
  target_price: 'Target price',
}

const VALUED_PRICE_KINDS: readonly PriceKind[] = ['discount_percent', 'target_price']

const SUBSTITUTE_LABEL: Record<Substitute, string> = {
  yes: 'Yes',
  no: 'No',
  unknown: 'Not stated',
}

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : DATE_FORMAT.format(date)
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function substituteOf(value: boolean | null): Substitute {
  if (value === null) return 'unknown'
  return value ? 'yes' : 'no'
}

function toDraft(fields: ParsedFields): Draft {
  return {
    customer: fields.customer ?? '',
    product_code: fields.product_code ?? '',
    quantity: fields.quantity === null ? '' : String(fields.quantity),
    deadline: fields.deadline ?? '',
    substitute: substituteOf(fields.substitute_allowed),
    price_kind: fields.price_kind,
    price_value: fields.price_value ?? '',
  }
}

function sameDraft(a: Draft, b: Draft): boolean {
  return DRAFT_KEYS.every((key) => a[key] === b[key])
}

// Range checks (quantity ≥ 1, discount ≤ 100, …) stay with the API, whose 422 message
// is shown at the form; here only what cannot be sent as a value at all.
function buildFields(
  draft: Draft,
  current: ParsedFields,
): { fields: ParsedFields } | { error: string } {
  const quantity = draft.quantity.trim()
  if (quantity !== '' && !/^\d+$/.test(quantity)) {
    return { error: 'Quantity must be a whole number.' }
  }
  let priceValue: string | null = null
  if (VALUED_PRICE_KINDS.includes(draft.price_kind)) {
    priceValue = draft.price_value.trim().replace(',', '.')
    if (priceValue === '') return { error: 'Enter a value for the price expectation.' }
    if (!/^\d+(\.\d+)?$/.test(priceValue)) return { error: 'Price value must be a number.' }
  }
  return {
    fields: {
      customer: draft.customer.trim() || null,
      product_code: draft.product_code.trim() || null,
      quantity: quantity === '' ? null : Number(quantity),
      deadline: draft.deadline || null,
      deadline_text: current.deadline_text,
      substitute_allowed: draft.substitute === 'unknown' ? null : draft.substitute === 'yes',
      price_kind: draft.price_kind,
      price_value: priceValue,
      price_text: current.price_text,
    },
  }
}

function emptyOr(value: string | null): string {
  return value === null || value === '' ? '(empty)' : value
}

function formatPrice(kind: PriceKind, value: string | null): string {
  if (kind === 'discount_percent' && value !== null) return `Discount ${value}%`
  if (kind === 'target_price' && value !== null) return `Target price ${value}`
  return PRICE_KIND_LABEL[kind]
}

// How the model's value of a field reads next to the "edited" mark.
function modelValue(field: FieldName, fields: ParsedFields): string {
  switch (field) {
    case 'customer':
      return emptyOr(fields.customer)
    case 'product_code':
      return emptyOr(fields.product_code)
    case 'quantity':
      return fields.quantity === null ? '(empty)' : String(fields.quantity)
    case 'deadline':
      return emptyOr(fields.deadline)
    case 'substitute_allowed':
      return SUBSTITUTE_LABEL[substituteOf(fields.substitute_allowed)]
    case 'price':
      return formatPrice(fields.price_kind, fields.price_value)
  }
}

// Decimal strings from the API (may be in exponent form, e.g. "1E-7").
function formatUsd(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `$${value}`
  const [whole, fraction = ''] = amount.toFixed(10).split('.')
  return `$${whole}.${fraction.replace(/0+$/, '').padEnd(2, '0')}`
}

function formatMs(ms: number): string {
  return `${ms < 10 ? ms.toFixed(1) : Math.round(ms)} ms`
}

function stepCost(step: StepSummary): string {
  if (step.price_status === 'not_applicable') return '—'
  if (step.price_status === 'unpriced' || step.cost_usd === null) return 'not priced'
  return `${formatUsd(step.cost_usd)} list price`
}

function totalCost(run: RunSummary): string {
  const anyPriced = run.steps.some((step) => step.price_status === 'priced')
  if (!anyPriced) return run.totals.cost_complete ? '—' : 'not priced'
  const cost = `${formatUsd(run.totals.cost_usd)} list price`
  return run.totals.cost_complete ? cost : `${cost} (some steps not priced)`
}

function Metrics({ run }: { run: RunSummary | null }) {
  if (run === null) return <p className="muted">Metrics unavailable</p>
  const totals = run.totals
  return (
    <section className="metrics" aria-label="Metrics">
      <h4 className="analysis__subheading">Metrics</h4>
      <ul className="metrics__steps">
        {run.steps.map((step) => (
          <li key={step.id} className="metrics__step">
            <p className="metrics__name">
              {step.name} <span className="muted">· {step.kind}</span>
              {step.status === 'failed' && (
                <span className="error">
                  {' '}
                  · failed{step.error_type ? ` (${step.error_type})` : ''}
                </span>
              )}
            </p>
            <dl className="metrics__list">
              <dt>Model</dt>
              <dd>{step.model ?? '—'}</dd>
              <dt>Tokens</dt>
              <dd>
                {step.input_tokens} in / {step.output_tokens} out
              </dd>
              <dt>Cost</dt>
              <dd>{stepCost(step)}</dd>
              <dt>Duration</dt>
              <dd>{formatMs(step.duration_ms)}</dd>
            </dl>
          </li>
        ))}
        <li className="metrics__step metrics__step--total">
          <p className="metrics__name">Total</p>
          <dl className="metrics__list">
            <dt>Tokens</dt>
            <dd>
              {totals.input_tokens} in / {totals.output_tokens} out
            </dd>
            <dt>Cost</dt>
            <dd>{totalCost(run)}</dd>
            <dt>Duration</dt>
            <dd>{formatMs(totals.duration_ms ?? totals.steps_duration_ms)}</dd>
          </dl>
        </li>
      </ul>
    </section>
  )
}

type FieldProps = {
  name: FieldName
  label: string
  inputId: string
  analysis: Analysis
  reviewed: readonly FieldName[]
  onReviewed: (field: FieldName, checked: boolean) => void
  children: ReactNode
}

function Field({ name, label, inputId, analysis, reviewed, onReviewed, children }: FieldProps) {
  const reason = analysis.uncertain[name]
  const edited = analysis.corrected_fields.includes(name)
  return (
    <div className={reason === undefined ? 'field' : 'field field--uncertain'}>
      <div className="field__label">
        <label htmlFor={inputId}>{label}</label>
        {edited && (
          <span className="field__edited">
            edited · model: {modelValue(name, analysis.model_fields)}
          </span>
        )}
      </div>
      {children}
      {reason !== undefined && (
        <div className="field__uncertain">
          <p className="field__reason">Uncertain: {reason}</p>
          <label className="field__check">
            <input
              type="checkbox"
              checked={reviewed.includes(name)}
              onChange={(event) => onReviewed(name, event.target.checked)}
            />
            Looks right
          </label>
        </div>
      )}
    </div>
  )
}

function AnalysisPanel({ inquiryId, onUnauthorized }: Props) {
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [reviewed, setReviewed] = useState<FieldName[]>([])
  const [busy, setBusy] = useState<'analyzing' | 'saving' | null>(null)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchAnalysis(inquiryId, controller.signal).then(
      (analysis) => {
        setLoad({ kind: 'ok', analysis })
        setDraft(analysis === null ? null : toDraft(analysis.fields))
        setReviewed([])
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onUnauthorized()
        else setLoad({ kind: 'error', message: errorMessage(error) })
      },
    )
    return () => controller.abort()
  }, [inquiryId, loadAttempt, onUnauthorized])

  function show(analysis: Analysis) {
    setLoad({ kind: 'ok', analysis })
    setDraft(toDraft(analysis.fields))
    setReviewed([])
  }

  function reload() {
    setLoad({ kind: 'loading' })
    setLoadAttempt((n) => n + 1)
  }

  const analysis = load.kind === 'ok' ? load.analysis : null
  const dirty = analysis !== null && draft !== null && !sameDraft(draft, toDraft(analysis.fields))
  const hasCorrections =
    analysis !== null && (analysis.corrected_at !== null || analysis.corrected_fields.length > 0)

  async function runAnalysis() {
    setConfirming(false)
    setBusy('analyzing')
    setAnalyzeError(null)
    setFormError(null)
    setNotice(null)
    try {
      show(await analyzeInquiry(inquiryId))
    } catch (error) {
      if (error instanceof UnauthorizedError) onUnauthorized()
      else setAnalyzeError(errorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  function requestReanalysis() {
    if (hasCorrections || dirty || reviewed.length > 0) setConfirming(true)
    else void runAnalysis()
  }

  async function save() {
    if (analysis === null || draft === null) return
    const built = buildFields(draft, analysis.fields)
    if ('error' in built) {
      setFormError(built.error)
      return
    }
    setBusy('saving')
    setFormError(null)
    setNotice(null)
    setConfirming(false)
    try {
      show(await saveCorrections(inquiryId, built.fields, reviewed, analysis.analyzed_at))
      setNotice('Corrections saved')
    } catch (error) {
      if (error instanceof UnauthorizedError) onUnauthorized()
      else if (error instanceof ApiError && error.status === 409) {
        setNotice('Analysis changed, reload')
        reload()
      } else setFormError(errorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => (current === null ? current : { ...current, [key]: value }))
  }

  function setFieldReviewed(field: FieldName, checked: boolean) {
    setReviewed((current) =>
      checked ? [...current, field] : current.filter((name) => name !== field),
    )
  }

  const id = (name: string) => `analysis-${inquiryId}-${name}`

  function renderResult(analysis: Analysis, draft: Draft) {
    const fieldProps = { analysis, reviewed, onReviewed: setFieldReviewed }
    return (
      <>
        {analysis.extractor === 'fake' && (
          <p className="analysis__banner">Rule-based demo parser (no LLM)</p>
        )}
        <p className="analysis__meta">
          Analyzed {formatDate(analysis.analyzed_at)}
          {analysis.analyzed_by_name && ` by ${analysis.analyzed_by_name}`}
          {analysis.corrected_at && (
            <>
              {' · '}corrected {formatDate(analysis.corrected_at)}
              {analysis.corrected_by_name && ` by ${analysis.corrected_by_name}`}
            </>
          )}
        </p>

        <form
          className="analysis__form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <Field name="customer" label="Customer" inputId={id('customer')} {...fieldProps}>
            <input
              id={id('customer')}
              value={draft.customer}
              onChange={(event) => update('customer', event.target.value)}
            />
          </Field>
          <Field name="product_code" label="Product" inputId={id('product')} {...fieldProps}>
            <input
              id={id('product')}
              value={draft.product_code}
              onChange={(event) => update('product_code', event.target.value)}
            />
          </Field>
          <Field name="quantity" label="Quantity" inputId={id('quantity')} {...fieldProps}>
            <input
              id={id('quantity')}
              inputMode="numeric"
              value={draft.quantity}
              onChange={(event) => update('quantity', event.target.value)}
            />
          </Field>
          <Field name="deadline" label="Deadline" inputId={id('deadline')} {...fieldProps}>
            <div className="field__row">
              <input
                id={id('deadline')}
                type="date"
                value={draft.deadline}
                onChange={(event) => update('deadline', event.target.value)}
              />
              {analysis.fields.deadline_text && (
                <span className="field__phrase">“{analysis.fields.deadline_text}”</span>
              )}
            </div>
          </Field>
          <Field
            name="substitute_allowed"
            label="Substitute allowed"
            inputId={id('substitute')}
            {...fieldProps}
          >
            <select
              id={id('substitute')}
              value={draft.substitute}
              onChange={(event) => update('substitute', event.target.value as Substitute)}
            >
              {(Object.keys(SUBSTITUTE_LABEL) as Substitute[]).map((value) => (
                <option key={value} value={value}>
                  {SUBSTITUTE_LABEL[value]}
                </option>
              ))}
            </select>
          </Field>
          <Field name="price" label="Price expectation" inputId={id('price-kind')} {...fieldProps}>
            <div className="field__row">
              <select
                id={id('price-kind')}
                value={draft.price_kind}
                onChange={(event) => update('price_kind', event.target.value as PriceKind)}
              >
                {(Object.keys(PRICE_KIND_LABEL) as PriceKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {PRICE_KIND_LABEL[kind]}
                  </option>
                ))}
              </select>
              {VALUED_PRICE_KINDS.includes(draft.price_kind) && (
                <input
                  aria-label={
                    draft.price_kind === 'discount_percent' ? 'Discount percent' : 'Target price'
                  }
                  inputMode="decimal"
                  className="field__value"
                  value={draft.price_value}
                  onChange={(event) => update('price_value', event.target.value)}
                />
              )}
            </div>
            {analysis.fields.price_text && (
              <span className="field__phrase">“{analysis.fields.price_text}”</span>
            )}
          </Field>

          {formError && (
            <p className="error" role="alert">
              {formError}
            </p>
          )}

          <div className="analysis__actions">
            <button type="submit" disabled={busy !== null || !(dirty || reviewed.length > 0)}>
              {busy === 'saving' ? 'Saving…' : 'Save corrections'}
            </button>
            <button type="button" onClick={requestReanalysis} disabled={busy !== null}>
              {busy === 'analyzing' ? 'Analyzing…' : 'Re-analyze'}
            </button>
          </div>
          {confirming && (
            <div className="analysis__confirm">
              <p>Corrections will be lost.</p>
              <div className="analysis__actions">
                <button type="button" onClick={runAnalysis} disabled={busy !== null}>
                  Re-analyze anyway
                </button>
                <button type="button" onClick={() => setConfirming(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </form>

        <Metrics run={analysis.run} />
      </>
    )
  }

  return (
    <section className="analysis" aria-labelledby={id('heading')}>
      <h3 id={id('heading')} className="analysis__heading">
        Analysis
      </h3>

      {load.kind === 'loading' && <p className="muted">Loading analysis…</p>}
      {load.kind === 'error' && (
        <div role="alert" className="analysis__problem">
          <p className="error">{load.message}</p>
          <button type="button" onClick={reload}>
            Retry
          </button>
        </div>
      )}
      {notice && (
        <p className="analysis__notice" role="status">
          {notice}
        </p>
      )}
      {analyzeError && (
        <div role="alert" className="analysis__problem">
          <p className="error">{analyzeError}</p>
          <button type="button" onClick={runAnalysis} disabled={busy !== null}>
            Retry
          </button>
        </div>
      )}

      {load.kind === 'ok' && analysis === null && (
        <div className="analysis__actions">
          <button type="button" onClick={runAnalysis} disabled={busy !== null}>
            {busy === 'analyzing' ? 'Analyzing…' : 'Analyze request'}
          </button>
        </div>
      )}

      {analysis !== null && draft !== null && renderResult(analysis, draft)}
    </section>
  )
}

export default AnalysisPanel
