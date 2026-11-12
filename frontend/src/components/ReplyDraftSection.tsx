import { useState } from 'react'
import type {
  LineSource,
  PolicyOutcome,
  PolicyResult,
  RecommendationOption,
  RecommendationView,
  ReplyDraftAction,
  ReplyDraftDecision,
  ReplyDraftEdit,
  ReplyDraftOfferLine,
  ReplyDraftStatus,
  ReplyDraftView,
  RuleCode,
  RuleResult,
  RuleVerdict,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { formatDate, formatPercent, formatPln } from './format'
import RunMetrics from './RunMetrics'

type Decision = 'approve' | 'reject'

type Props = {
  inquiryId: number
  // null while there is no draft for the current recommendation.
  draft: ReplyDraftView | null
  // The recommendation the draft is built from; tells why there is none and lists the options
  // the offer can be edited to.
  recommendation: RecommendationView | null
  // True while the panel analyzes, saves, re-runs a stage, drafts or saves a decision.
  disabled: boolean
  // True while the panel regenerates the draft.
  drafting: boolean
  // True while the panel saves an edit or a decision.
  deciding: boolean
  // Regenerates the draft and shows the result; rejects when it failed.
  onRegenerate: () => Promise<void>
  // Saves an edit of the draft read at `updatedAt`; rejects when it failed.
  onEdit: (updatedAt: string, edit: ReplyDraftEdit) => Promise<void>
  // Approves or rejects the draft read at `updatedAt`; rejects when it failed.
  onDecide: (updatedAt: string, action: Decision, reason: string | null) => Promise<void>
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Every status is shown as text; the tone only adds the colour.
type Tone = 'ok' | 'warn' | 'error'

const STATUS: Record<ReplyDraftStatus, [string, Tone]> = {
  draft: ['Draft', 'warn'],
  ready_to_send: ['Ready to send (sending is simulated)', 'ok'],
  awaiting_supervisor: ['Awaiting supervisor approval', 'warn'],
  rejected: ['Rejected', 'error'],
}

const ACTION: Record<ReplyDraftAction, string> = {
  edit: 'Edited',
  approve: 'Approved',
  reject: 'Rejected',
}

const OUTCOME: Record<PolicyOutcome, [string, Tone]> = {
  no_approval_needed: ['No approval needed', 'ok'],
  requires_supervisor: ['Requires supervisor approval', 'warn'],
}

const RULE: Record<RuleCode, string> = {
  margin: 'Margin',
  discount: 'Discount',
  order_value: 'Order value',
  credit: 'Credit',
}

const VERDICT: Record<RuleVerdict, [string, Tone]> = {
  pass: ['Pass', 'ok'],
  fail: ['Fail', 'error'],
  not_evaluated: ['Not evaluated', 'warn'],
}

const SOURCE: Record<LineSource, string> = {
  stock: 'own stock',
  substitute_stock: 'substitute from stock',
  supplier: 'supplier',
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

// Why there cannot be a (current) draft; null when the recommendation allows one.
function blockedReason(recommendation: RecommendationView | null): string | null {
  if (recommendation === null) return 'No draft: there is no recommendation yet.'
  if (recommendation.status === 'failed' || recommendation.choice === null) {
    return 'No draft: the recommendation has no chosen option.'
  }
  if (recommendation.stale) {
    return 'No draft: the recommendation is out of date; re-run the recommendation first.'
  }
  return null
}

function sourceText(line: { source: LineSource; supplier: string | null }): string {
  return line.source === 'supplier' ? `supplier ${line.supplier ?? '—'}` : SOURCE[line.source]
}

function ruleAmount(rule: RuleResult, value: string | null): string {
  if (value === null) return '—'
  return rule.unit === 'percent' ? formatPercent(value) : formatPln(value)
}

// The reply draft of the recommended option: the e-mail preview, why this option, the policy
// verdict in force and the salesperson's decision.
function ReplyDraftSection({
  inquiryId,
  draft,
  recommendation,
  disabled,
  drafting,
  deciding,
  onRegenerate,
  onEdit,
  onDecide,
  onUnauthorized,
}: Props) {
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'approve' | 'reject' | 'edit' | null>(null)
  const headingId = `draft-${inquiryId}-heading`

  async function regenerate() {
    setError(null)
    setMode(null)
    try {
      await onRegenerate()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure))
    }
  }

  const blocked = blockedReason(recommendation)
  const outdated = draft === null || draft.stale
  const offerRegenerate =
    blocked === null && (draft === null || draft.status === 'rejected' || draft.stale)
  const canDecide = draft !== null && draft.status === 'draft' && !draft.stale

  return (
    <section className="orchestration draft" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Reply draft
      </h4>

      {blocked !== null && outdated && <p className="checks__line">{blocked}</p>}
      {blocked === null && draft === null && (
        <p className="checks__line">Draft not generated yet</p>
      )}
      {draft?.stale && (
        <p className="checks__line">
          The recommendation or its policy verdict changed after this draft was made; the draft
          may be out of date.
        </p>
      )}
      {offerRegenerate && (
        <div className="analysis__actions">
          <button type="button" onClick={regenerate} disabled={disabled}>
            {drafting ? 'Drafting…' : 'Regenerate draft'}
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Regenerating the draft failed: {error}</p>
          <button type="button" onClick={regenerate} disabled={disabled}>
            Retry
          </button>
        </div>
      )}

      {draft !== null && <DraftResult draft={draft} />}

      {draft !== null && canDecide && mode === null && (
        <div className="analysis__actions" role="group" aria-label="Decision">
          <button type="button" onClick={() => setMode('approve')} disabled={disabled}>
            Approve
          </button>
          <button type="button" onClick={() => setMode('edit')} disabled={disabled}>
            Edit offer
          </button>
          <button type="button" onClick={() => setMode('reject')} disabled={disabled}>
            Reject
          </button>
        </div>
      )}
      {draft !== null && canDecide && (mode === 'approve' || mode === 'reject') && (
        <DecisionForm
          key={`${mode}-${draft.updated_at}`}
          action={mode}
          disabled={disabled}
          saving={deciding}
          onSubmit={(reason) => onDecide(draft.updated_at, mode, reason)}
          onDone={() => setMode(null)}
          onUnauthorized={onUnauthorized}
        />
      )}
      {draft !== null && canDecide && mode === 'edit' && (
        <EditForm
          key={draft.updated_at}
          draft={draft}
          options={recommendation?.options ?? []}
          disabled={disabled}
          saving={deciding}
          onSubmit={(edit) => onEdit(draft.updated_at, edit)}
          onDone={() => setMode(null)}
          onUnauthorized={onUnauthorized}
        />
      )}
    </section>
  )
}

function DraftResult({ draft }: { draft: ReplyDraftView }) {
  const [status, tone] = STATUS[draft.status]
  const offer = draft.offer
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="checks__outcome">
          Status: <span className="draft__status">{status}</span>
        </p>
      </div>
      <p className="analysis__meta">
        Drafted {formatDate(draft.drafted_at)} · option {offer.option_id}
        {offer.edited && ' · edited offer'}
      </p>
      {draft.text_source === 'fallback' && (
        <p className="draft__fallback">
          The model’s paragraphs were unavailable; the draft uses the fixed fallback text.
        </p>
      )}

      <section className="draft__email" aria-label="E-mail preview">
        <p className="draft__subject">
          Subject: <span lang="pl">{draft.subject}</span>
        </p>
        <pre className="draft__body" lang="pl">
          {draft.body}
        </pre>
      </section>

      <dl className="metrics__list">
        <dt>Offer value</dt>
        <dd>{formatPln(offer.value)}</dd>
        <dt>Margin</dt>
        <dd>{formatPercent(offer.margin_percent)}</dd>
        <dt>Coverage</dt>
        <dd>
          {offer.covered_quantity} / {offer.requested_quantity} pcs
        </dd>
      </dl>

      {draft.why !== null && (
        <div className="draft__why">
          <p className="recommendation__why">Why this recommendation?</p>
          <p className="checks__line" lang="pl">
            {draft.why.justification}
          </p>
          {draft.why.signals.length > 0 && (
            <ul className="recommendation__signal-list" aria-label="Cited signals" lang="pl">
              {draft.why.signals.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <VerdictInForce policy={draft.policy} edited={offer.edited} />

      <RunMetrics run={draft.run} label="Draft metrics" />
    </>
  )
}

function VerdictInForce({ policy, edited }: { policy: PolicyResult | null; edited: boolean }) {
  const title = edited ? 'Policy verdict in force (edited offer)' : 'Policy verdict in force'
  if (policy === null) {
    return (
      <p className="checks__line">
        {title}: none — approval needs a current policy verdict.
      </p>
    )
  }
  const [outcome, tone] = OUTCOME[policy.outcome]
  return (
    <div className="policy__table-wrap">
      <table className="policy__table">
        <caption className="orchestration__stage-title">
          {title}: <span className={`check__status check__status--${tone}`}>{outcome}</span>
        </caption>
        <thead>
          <tr>
            <th scope="col">Rule</th>
            <th scope="col">Actual</th>
            <th scope="col">Threshold</th>
            <th scope="col">Verdict</th>
            <th scope="col">Reason</th>
          </tr>
        </thead>
        <tbody>
          {policy.rules.map((rule) => {
            const [verdict, verdictTone] = VERDICT[rule.verdict]
            return (
              <tr key={rule.code}>
                <th scope="row">{RULE[rule.code]}</th>
                <td>{ruleAmount(rule, rule.actual)}</td>
                <td>{ruleAmount(rule, rule.threshold)}</td>
                <td>
                  <span className={`check__status check__status--${verdictTone}`}>{verdict}</span>
                </td>
                <td>{rule.reason}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

type FormProps<T> = {
  disabled: boolean
  // True while the panel saves this form.
  saving: boolean
  // Sends the form; rejects when saving failed.
  onSubmit: (value: T) => Promise<void>
  // Closes the form after it was saved.
  onDone: () => void
  onUnauthorized: () => void
}

// Sends a form and closes it, or keeps it open with the error shown.
async function send<T>(
  props: FormProps<T>,
  value: T,
  setError: (error: string | null) => void,
): Promise<void> {
  setError(null)
  try {
    await props.onSubmit(value)
    props.onDone()
  } catch (failure) {
    if (failure instanceof UnauthorizedError) props.onUnauthorized()
    else setError(errorMessage(failure))
  }
}

// Approve with an optional comment, or reject with a required reason.
function DecisionForm(props: FormProps<string | null> & { action: Decision }) {
  const { action, disabled, saving, onDone } = props
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const approve = action === 'approve'
  const id = `draft-${action}-reason`

  function submit() {
    const text = reason.trim()
    if (!approve && text === '') {
      setError('Enter a reason for the rejection.')
      return
    }
    void send(props, text === '' ? null : text, setError)
  }

  return (
    <form
      className="draft__form"
      noValidate
      aria-label={approve ? 'Approve draft' : 'Reject draft'}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor={id}>{approve ? 'Comment (optional)' : 'Reason (required)'}</label>
      <textarea
        id={id}
        rows={2}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="analysis__actions">
        <button type="submit" disabled={disabled}>
          {saving ? 'Saving…' : approve ? 'Confirm approval' : 'Confirm rejection'}
        </button>
        <button type="button" onClick={onDone} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}

type LineDraft = { quantity: string; unit_price: string }

function lineDrafts(lines: { quantity: number; unit_price: string }[]): LineDraft[] {
  return lines.map((line) => ({ quantity: String(line.quantity), unit_price: line.unit_price }))
}

type EditProps = FormProps<ReplyDraftEdit> & {
  draft: ReplyDraftView
  // The recommendation's options; the offer can be edited to any of them.
  options: RecommendationOption[]
}

// Another option, quantities and unit prices of its lines, and a required reason. Range
// checks (quantity ≥ 1, price above zero) stay with the API, whose 422 message is shown here.
function EditForm(props: EditProps) {
  const { draft, options, disabled, saving, onDone } = props
  const offer = draft.offer
  const [optionId, setOptionId] = useState(offer.option_id)
  const [lines, setLines] = useState<LineDraft[]>(lineDrafts(offer.lines))
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const option = options.find((item) => item.id === optionId)
  // The current offer's lines carry its list prices; another option's only its own prices.
  const shown: (ReplyDraftOfferLine | RecommendationOption['lines'][number])[] =
    optionId === offer.option_id || option === undefined ? offer.lines : option.lines
  const choices = options.some((item) => item.id === offer.option_id)
    ? options
    : [{ id: offer.option_id }, ...options]

  function choose(id: string) {
    setOptionId(id)
    const next = options.find((item) => item.id === id)
    setLines(lineDrafts(id === offer.option_id || next === undefined ? offer.lines : next.lines))
  }

  function update(index: number, key: keyof LineDraft, value: string) {
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, [key]: value } : line)),
    )
  }

  function submit() {
    const built = []
    for (const [index, line] of lines.entries()) {
      const quantity = line.quantity.trim()
      const price = line.unit_price.trim().replace(',', '.')
      if (!/^\d+$/.test(quantity)) {
        setError('Quantity must be a whole number.')
        return
      }
      if (!/^\d+(\.\d{1,2})?$/.test(price)) {
        setError('Unit price must be a number with at most two decimal places.')
        return
      }
      built.push({
        product_code: shown[index].product_code,
        quantity: Number(quantity),
        unit_price: price,
      })
    }
    const text = reason.trim()
    if (text === '') {
      setError('Enter a reason for the edit.')
      return
    }
    void send(props, { option_id: optionId, lines: built, reason: text }, setError)
  }

  const id = (name: string) => `draft-edit-${name}`

  return (
    <form
      className="draft__form"
      noValidate
      aria-label="Edit offer"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor={id('option')}>Option</label>
      <select id={id('option')} value={optionId} onChange={(event) => choose(event.target.value)}>
        {choices.map((item) => (
          <option key={item.id} value={item.id}>
            {item.id}
          </option>
        ))}
      </select>

      <div className="policy__table-wrap">
        <table className="policy__table draft__lines">
          <caption className="orchestration__stage-title">Offer lines</caption>
          <thead>
            <tr>
              <th scope="col">Product</th>
              <th scope="col">Quantity</th>
              <th scope="col">Unit price (PLN)</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((line, index) => {
              const name = `${line.product_code}, ${sourceText(line)}`
              return (
                <tr key={`${line.source}-${line.product_code}-${index}`}>
                  <th scope="row">
                    {line.product_code} <span className="muted">· {sourceText(line)}</span>
                    {'list_price' in line && (
                      <span className="draft__list-price">
                        list {formatPln(line.list_price)}
                      </span>
                    )}
                  </th>
                  <td>
                    <input
                      aria-label={`Quantity of ${name}`}
                      inputMode="numeric"
                      value={lines[index]?.quantity ?? ''}
                      onChange={(event) => update(index, 'quantity', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Unit price of ${name}`}
                      inputMode="decimal"
                      value={lines[index]?.unit_price ?? ''}
                      onChange={(event) => update(index, 'unit_price', event.target.value)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <label htmlFor={id('reason')}>Reason (required)</label>
      <textarea
        id={id('reason')}
        rows={2}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="analysis__actions">
        <button type="submit" disabled={disabled}>
          {saving ? 'Saving…' : 'Save edit'}
        </button>
        <button type="button" onClick={onDone} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}

// Every decision on the inquiry's drafts, oldest first, also of earlier recommendations.
export function DecisionHistory({
  inquiryId,
  decisions,
}: {
  inquiryId: number
  decisions: ReplyDraftDecision[]
}) {
  const headingId = `decisions-${inquiryId}-heading`
  return (
    <section className="orchestration draft__history" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Decision history
      </h4>
      <ol className="checks__list">
        {decisions.map((decision, index) => {
          const [status, tone] = STATUS[decision.status_after]
          const outcome = decision.snapshot.policy_outcome
          const failing = decision.snapshot.failing_rules.map((code) => RULE[code])
          return (
            <li key={`${decision.decided_at}-${index}`} className="check">
              <p className="check__head">
                <span className="check__name">
                  {ACTION[decision.action]}
                  {!decision.current && <span className="draft__earlier">earlier version</span>}
                </span>
                <span className={`check__status check__status--${tone}`}>{status}</span>
              </p>
              <dl className="metrics__list">
                <dt>By</dt>
                <dd>{decision.decided_by_name ?? 'Unknown user'}</dd>
                <dt>When</dt>
                <dd>{formatDate(decision.decided_at)}</dd>
                <dt>Reason</dt>
                <dd>{decision.reason ?? '—'}</dd>
                <dt>Offer</dt>
                <dd>
                  {formatPln(decision.snapshot.offer.value)} · option{' '}
                  {decision.snapshot.offer.option_id}
                </dd>
                <dt>Policy</dt>
                <dd>
                  {outcome === null ? 'no verdict' : OUTCOME[outcome][0]}
                  {failing.length > 0 && ` (failing: ${failing.join(', ')})`}
                </dd>
              </dl>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

export default ReplyDraftSection
