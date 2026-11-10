import { useState, type ReactNode } from 'react'
import {
  rerunChecks,
  type Analysis,
  type CheckInput,
  type ChecksView,
  type CreditCheck,
  type CustomerCheck,
  type DiscountCheck,
  type NeedsInputReason,
  type PriceCheck,
  type StockCheck,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { formatDate, totalCost, totalDuration } from './format'
import RunMetrics from './RunMetrics'

type Props = {
  inquiryId: number
  analysis: Analysis
  // True while the panel analyzes or saves: the checks are about to be replaced.
  disabled: boolean
  // Called with the analysis returned by a re-run of the checks.
  onRerun: (analysis: Analysis) => void
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Every status is shown as text; the tone only adds the colour.
type Tone = 'ok' | 'warn' | 'error' | 'muted'

const INPUT_LABEL: Record<CheckInput, string> = {
  customer: 'Customer',
  product_code: 'Product',
  quantity: 'Quantity',
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

// Decimal strings from the API, e.g. "5.00" → "5", "10.50" → "10.5".
function formatPercent(value: string): string {
  const trimmed = value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value
  return `${trimmed}%`
}

function formatPln(value: string | null): string {
  return value === null ? '—' : `${value} PLN`
}

function formatCount(value: number | null): string {
  return value === null ? '—' : String(value)
}

function reasonText(reason: NeedsInputReason, checks: ChecksView): string {
  const { customer, stock } = checks.results
  switch (reason) {
    case 'customer_missing':
      return 'Customer missing — no name in the inquiry and the sender’s e-mail domain is not in records'
    case 'customer_not_found':
      return 'Customer not found in records'
    case 'customer_ambiguous':
      return `Customer matches several records: ${customer.candidates.join(', ')}`
    case 'product_missing':
      return 'Product code missing'
    case 'product_not_found':
      return stock.product_code === null
        ? 'Product not found in the catalogue'
        : `Product ${stock.product_code} not found in the catalogue`
    case 'quantity_missing':
      return 'Quantity missing'
  }
}

function substituteText(allowed: boolean | null): string {
  if (allowed === null) return 'Substitute: not stated in the inquiry'
  return allowed ? 'Substitute: the customer accepts one' : 'Substitute: the customer does not accept one'
}

function Banner({ checks, analysis }: { checks: ChecksView; analysis: Analysis }) {
  if (checks.outcome === 'standard') {
    const run = checks.run
    return (
      <div className="checks__banner checks__banner--standard">
        <p className="checks__outcome">Standard inquiry — completed without agents</p>
        {run !== null && (
          <dl className="metrics__list">
            <dt>Tokens</dt>
            <dd>
              {run.totals.input_tokens} in / {run.totals.output_tokens} out
            </dd>
            <dt>Cost</dt>
            <dd>{totalCost(run)}</dd>
            <dt>Duration</dt>
            <dd>{totalDuration(run)}</dd>
            <dt>Steps</dt>
            <dd>{run.steps.length}</dd>
          </dl>
        )}
      </div>
    )
  }
  if (checks.outcome === 'exception') {
    const stock = checks.results.stock
    return (
      <div className="checks__banner checks__banner--exception">
        <p className="checks__outcome">
          Exception: insufficient stock — requested {formatCount(stock.requested)}, available{' '}
          {formatCount(stock.available)} (short {formatCount(stock.shortage)})
        </p>
        <p className="checks__line">Handed over to orchestration (not available yet)</p>
        <p className="checks__line">{substituteText(analysis.fields.substitute_allowed)}</p>
      </div>
    )
  }
  return (
    <div className="checks__banner checks__banner--needs-input">
      <p className="checks__outcome">Needs input</p>
      <ul className="checks__reasons">
        {checks.reasons.map((reason) => (
          <li key={reason}>{reasonText(reason, checks)}</li>
        ))}
      </ul>
    </div>
  )
}

type CheckItemProps = {
  name: string
  status: string
  tone: Tone
  children?: ReactNode
}

function CheckItem({ name, status, tone, children }: CheckItemProps) {
  return (
    <li className="check">
      <p className="check__head">
        <span className="check__name">{name}</span>
        <span className={`check__status check__status--${tone}`}>{status}</span>
      </p>
      {children !== undefined && <dl className="metrics__list">{children}</dl>}
    </li>
  )
}

function CustomerItem({ check }: { check: CustomerCheck }) {
  switch (check.status) {
    case 'matched':
      return (
        <CheckItem name="Customer" status="Matched" tone="ok">
          <dt>Name</dt>
          <dd>{check.name ?? '—'}</dd>
          <dt>Matched by</dt>
          <dd>{check.matched_by === 'email' ? 'e-mail' : 'name'}</dd>
        </CheckItem>
      )
    case 'ambiguous':
      return (
        <CheckItem name="Customer" status="Ambiguous" tone="warn">
          <dt>Candidates</dt>
          <dd>{check.candidates.join(', ')}</dd>
        </CheckItem>
      )
    case 'not_found':
      return <CheckItem name="Customer" status="Not found" tone="warn" />
    case 'missing':
      return <CheckItem name="Customer" status="Missing" tone="warn" />
  }
}

function StockItem({ check }: { check: StockCheck }) {
  if (check.status === 'skipped') return <CheckItem name="Stock" status="—" tone="muted" />
  return (
    <CheckItem
      name="Stock"
      status={check.status === 'ok' ? 'In stock' : 'Insufficient'}
      tone={check.status === 'ok' ? 'ok' : 'error'}
    >
      <dt>Product</dt>
      <dd>
        {check.product_code}
        {check.product_name && ` · ${check.product_name}`}
      </dd>
      <dt>Requested</dt>
      <dd>{formatCount(check.requested)}</dd>
      <dt>Available</dt>
      <dd>{formatCount(check.available)}</dd>
      {check.status === 'insufficient' && (
        <>
          <dt>Short</dt>
          <dd>{formatCount(check.shortage)}</dd>
        </>
      )}
    </CheckItem>
  )
}

function PriceItem({ check }: { check: PriceCheck }) {
  if (check.status === 'skipped') return <CheckItem name="Price" status="—" tone="muted" />
  return (
    <CheckItem name="Price" status="Calculated" tone="ok">
      <dt>List price</dt>
      <dd>{formatPln(check.list_price)}</dd>
      <dt>Discount</dt>
      <dd>{check.discount_percent === null ? '—' : formatPercent(check.discount_percent)}</dd>
      <dt>Unit price</dt>
      <dd>{formatPln(check.unit_price)}</dd>
      <dt>Value</dt>
      <dd>{check.total === null ? '— (no quantity)' : formatPln(check.total)}</dd>
    </CheckItem>
  )
}

function requestedDiscount(check: DiscountCheck): string {
  const value = check.requested_value
  switch (check.requested_kind) {
    case 'discount_percent':
      return value === null ? 'a discount' : formatPercent(value)
    case 'target_price':
      return value === null ? 'a target price' : `target price ${formatPln(value)}`
    case 'best_price':
      return 'best price (no value)'
    case 'none':
      return 'not stated'
  }
}

function DiscountItem({ check }: { check: DiscountCheck }) {
  if (check.status === 'skipped') return <CheckItem name="Discount" status="—" tone="muted" />
  const above = check.status === 'above_standard'
  return (
    <CheckItem
      name="Discount"
      status={above ? 'Above standard' : 'Within standard'}
      tone={above ? 'warn' : 'ok'}
    >
      <dt>Standard</dt>
      <dd>{check.standard_percent === null ? '—' : formatPercent(check.standard_percent)}</dd>
      <dt>Requested</dt>
      <dd>{requestedDiscount(check)}</dd>
    </CheckItem>
  )
}

const CREDIT_STATUS: Record<Exclude<CreditCheck['status'], 'skipped'>, [string, Tone]> = {
  ok: ['Within limit', 'ok'],
  over_limit: ['Over limit', 'warn'],
  blocked: ['Blocked', 'warn'],
}

function CreditItem({ check }: { check: CreditCheck }) {
  if (check.status === 'skipped') return <CheckItem name="Credit" status="—" tone="muted" />
  const [status, tone] = CREDIT_STATUS[check.status]
  return (
    <CheckItem name="Credit" status={status} tone={tone}>
      <dt>Limit</dt>
      <dd>{formatPln(check.limit)}</dd>
      <dt>Balance</dt>
      <dd>{formatPln(check.balance)}</dd>
      <dt>Order value</dt>
      <dd>{formatPln(check.order_value)}</dd>
    </CheckItem>
  )
}

function ChecksSection({ inquiryId, analysis, disabled, onRerun, onUnauthorized }: Props) {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const checks = analysis.checks
  const headingId = `checks-${inquiryId}-heading`

  async function rerun() {
    setRunning(true)
    setError(null)
    try {
      onRerun(await rerunChecks(inquiryId))
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure))
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="checks" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Checks
      </h4>

      {(checks === null || checks.stale) && (
        <div className="checks__stale">
          <p>
            {checks === null
              ? 'No check result for this analysis yet.'
              : 'The analysis changed after these checks ran; the result may be out of date.'}
          </p>
          <div className="analysis__actions">
            <button type="button" onClick={rerun} disabled={running || disabled}>
              {running ? 'Running checks…' : 'Re-run checks'}
            </button>
          </div>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Re-running the checks failed: {error}</p>
          <button type="button" onClick={rerun} disabled={running || disabled}>
            Retry
          </button>
        </div>
      )}

      {checks !== null && (
        <>
          <Banner checks={checks} analysis={analysis} />
          {checks.uncertain_inputs.length > 0 && (
            <p className="checks__uncertain">
              Based on uncertain fields:{' '}
              {checks.uncertain_inputs.map((input) => INPUT_LABEL[input]).join(', ')}
            </p>
          )}
          <p className="analysis__meta">Checked {formatDate(checks.checked_at)}</p>
          <ul className="checks__list" aria-label="Individual checks">
            <CustomerItem check={checks.results.customer} />
            <StockItem check={checks.results.stock} />
            <PriceItem check={checks.results.price} />
            <DiscountItem check={checks.results.discount} />
            <CreditItem check={checks.results.credit} />
          </ul>
          <RunMetrics run={checks.run} label="Checks metrics" />
        </>
      )}
    </section>
  )
}

export default ChecksSection
