import { useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import {
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
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate, formatPercent, formatPln } from './format'

type Props = {
  inquiryId: number
  analysis: Analysis
  // True while the panel analyzes, saves or re-runs anything.
  disabled: boolean
  // True while the panel re-runs the checks.
  running: boolean
  // Re-runs the checks and shows the result; rejects when the re-run failed.
  onRerun: () => Promise<void>
  // True when re-running the checks is the step's primary action (outline otherwise).
  primary?: boolean
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Every status is shown as text; the tone only adds the colour.
type Tone = 'ok' | 'warn' | 'error' | 'muted'

const INPUT_KEY = {
  customer: 'checks.input.customer',
  product_code: 'checks.input.product_code',
  quantity: 'checks.input.quantity',
} as const satisfies Record<CheckInput, string>

function formatCount(value: number | null): string {
  return value === null ? '—' : String(value)
}

function reasonText(reason: NeedsInputReason, checks: ChecksView, t: TFunction): string {
  const { customer, stock } = checks.results
  switch (reason) {
    case 'customer_missing':
      return t('checks.reason.customer_missing')
    case 'customer_not_found':
      return t('checks.reason.customer_not_found')
    case 'customer_ambiguous':
      return t('checks.reason.customer_ambiguous', {
        candidates: customer.candidates.join(', '),
      })
    case 'product_missing':
      return t('checks.reason.product_missing')
    case 'product_not_found':
      return stock.product_code === null
        ? t('checks.reason.product_not_found')
        : t('checks.reason.product_not_found_code', {
            code: stock.product_code,
          })
    case 'quantity_missing':
      return t('checks.reason.quantity_missing')
  }
}

function substituteText(allowed: boolean | null, t: TFunction): string {
  if (allowed === null) return t('checks.substitute.unknown')
  return allowed ? t('checks.substitute.yes') : t('checks.substitute.no')
}

function Banner({ checks, analysis }: { checks: ChecksView; analysis: Analysis }) {
  const { t } = useTranslation()
  if (checks.outcome === 'standard') {
    return (
      <div className="checks__banner checks__banner--standard">
        <p className="checks__outcome">{t('checks.standard')}</p>
      </div>
    )
  }
  if (checks.outcome === 'exception') {
    const stock = checks.results.stock
    return (
      <div className="checks__banner checks__banner--exception">
        <p className="checks__outcome">
          {t('checks.exception', {
            requested: formatCount(stock.requested),
            available: formatCount(stock.available),
            shortage: formatCount(stock.shortage),
          })}
        </p>
        <p className="checks__line">{substituteText(analysis.fields.substitute_allowed, t)}</p>
      </div>
    )
  }
  return (
    <div className="checks__banner checks__banner--needs-input">
      <p className="checks__outcome">{t('checks.needsInput')}</p>
      <ul className="checks__reasons list-disc ps-5">
        {checks.reasons.map((reason) => (
          <li key={reason}>{reasonText(reason, checks, t)}</li>
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
  const { t } = useTranslation()
  const name = t('checks.customer.name')
  switch (check.status) {
    case 'matched':
      return (
        <CheckItem name={name} status={t('checks.customer.matched')} tone="ok">
          <dt>{t('checks.customer.nameField')}</dt>
          <dd>{check.name ?? '—'}</dd>
          <dt>{t('checks.customer.matchedBy')}</dt>
          <dd>
            {check.matched_by === 'email'
              ? t('checks.customer.byEmail')
              : t('checks.customer.byName')}
          </dd>
        </CheckItem>
      )
    case 'ambiguous':
      return (
        <CheckItem name={name} status={t('checks.customer.ambiguous')} tone="warn">
          <dt>{t('checks.customer.candidates')}</dt>
          <dd>{check.candidates.join(', ')}</dd>
        </CheckItem>
      )
    case 'not_found':
      return <CheckItem name={name} status={t('checks.customer.notFound')} tone="warn" />
    case 'missing':
      return <CheckItem name={name} status={t('checks.customer.missing')} tone="warn" />
  }
}

function StockItem({ check }: { check: StockCheck }) {
  const { t } = useTranslation()
  const name = t('checks.stock.name')
  if (check.status === 'skipped') return <CheckItem name={name} status="—" tone="muted" />
  return (
    <CheckItem
      name={name}
      status={check.status === 'ok' ? t('checks.stock.inStock') : t('checks.stock.insufficient')}
      tone={check.status === 'ok' ? 'ok' : 'error'}
    >
      <dt>{t('checks.stock.product')}</dt>
      <dd>
        {check.product_code}
        {check.product_name && ` · ${check.product_name}`}
      </dd>
      <dt>{t('checks.stock.requested')}</dt>
      <dd>{formatCount(check.requested)}</dd>
      <dt>{t('checks.stock.available')}</dt>
      <dd>{formatCount(check.available)}</dd>
      {check.status === 'insufficient' && (
        <>
          <dt>{t('checks.stock.short')}</dt>
          <dd>{formatCount(check.shortage)}</dd>
        </>
      )}
    </CheckItem>
  )
}

function PriceItem({ check }: { check: PriceCheck }) {
  const { t } = useTranslation()
  const name = t('checks.price.name')
  if (check.status === 'skipped') return <CheckItem name={name} status="—" tone="muted" />
  return (
    <CheckItem name={name} status={t('checks.price.calculated')} tone="ok">
      <dt>{t('checks.price.listPrice')}</dt>
      <dd>{formatPln(check.list_price)}</dd>
      <dt>{t('checks.price.discount')}</dt>
      <dd>{check.discount_percent === null ? '—' : formatPercent(check.discount_percent)}</dd>
      <dt>{t('checks.price.unitPrice')}</dt>
      <dd>{formatPln(check.unit_price)}</dd>
      <dt>{t('checks.price.value')}</dt>
      <dd>{check.total === null ? t('checks.price.noQuantity') : formatPln(check.total)}</dd>
    </CheckItem>
  )
}

function requestedDiscount(check: DiscountCheck, t: TFunction): string {
  const value = check.requested_value
  switch (check.requested_kind) {
    case 'discount_percent':
      return value === null ? t('checks.discount.aDiscount') : formatPercent(value)
    case 'target_price':
      return value === null
        ? t('checks.discount.aTargetPrice')
        : t('checks.discount.targetPrice', { value: formatPln(value) })
    case 'best_price':
      return t('checks.discount.bestPrice')
    case 'none':
      return t('checks.discount.notStated')
  }
}

function DiscountItem({ check }: { check: DiscountCheck }) {
  const { t } = useTranslation()
  const name = t('checks.discount.name')
  if (check.status === 'skipped') return <CheckItem name={name} status="—" tone="muted" />
  const above = check.status === 'above_standard'
  return (
    <CheckItem
      name={name}
      status={above ? t('checks.discount.above') : t('checks.discount.within')}
      tone={above ? 'warn' : 'ok'}
    >
      <dt>{t('checks.discount.standard')}</dt>
      <dd>{check.standard_percent === null ? '—' : formatPercent(check.standard_percent)}</dd>
      <dt>{t('checks.discount.requested')}</dt>
      <dd>{requestedDiscount(check, t)}</dd>
    </CheckItem>
  )
}

const CREDIT_STATUS = {
  ok: ['checks.credit.within', 'ok'],
  over_limit: ['checks.credit.over', 'warn'],
  blocked: ['checks.credit.blocked', 'warn'],
} as const satisfies Record<Exclude<CreditCheck['status'], 'skipped'>, [string, Tone]>

function CreditItem({ check }: { check: CreditCheck }) {
  const { t } = useTranslation()
  const name = t('checks.credit.name')
  if (check.status === 'skipped') return <CheckItem name={name} status="—" tone="muted" />
  const [statusKey, tone] = CREDIT_STATUS[check.status]
  return (
    <CheckItem name={name} status={t(statusKey)} tone={tone}>
      <dt>{t('checks.credit.limit')}</dt>
      <dd>{formatPln(check.limit)}</dd>
      <dt>{t('checks.credit.balance')}</dt>
      <dd>{formatPln(check.balance)}</dd>
      <dt>{t('checks.credit.orderValue')}</dt>
      <dd>{formatPln(check.order_value)}</dd>
    </CheckItem>
  )
}

function ChecksSection({
  inquiryId,
  analysis,
  disabled,
  running,
  onRerun,
  primary = false,
  onUnauthorized,
}: Props) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const checks = analysis.checks
  const headingId = `checks-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure, t))
    }
  }

  return (
    <section className="checks" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        {t('checks.heading')}
      </h4>

      {(checks === null || checks.stale) && (
        <div className="checks__stale">
          <p>{checks === null ? t('checks.noResult') : t('checks.stale')}</p>
          <div className="analysis__actions">
            <Button
              type="button"
              variant={primary ? 'default' : 'outline'}
              onClick={rerun}
              disabled={disabled}
            >
              {running ? t('checks.running') : t('checks.rerun')}
            </Button>
          </div>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">{t('checks.rerunFailed', { message: error })}</p>
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {checks !== null && (
        <>
          <Banner checks={checks} analysis={analysis} />
          {checks.uncertain_inputs.length > 0 && (
            <p className="checks__uncertain">
              {t('checks.uncertainBasis', {
                fields: checks.uncertain_inputs.map((input) => t(INPUT_KEY[input])).join(', '),
              })}
            </p>
          )}
          <p className="analysis__meta">
            {t('checks.checked', { date: formatDate(checks.checked_at) })}
          </p>
          <ul className="checks__list" aria-label={t('checks.listLabel')}>
            <CustomerItem check={checks.results.customer} />
            <StockItem check={checks.results.stock} />
            <PriceItem check={checks.results.price} />
            <DiscountItem check={checks.results.discount} />
            <CreditItem check={checks.results.credit} />
          </ul>
        </>
      )}
    </section>
  )
}

export default ChecksSection
