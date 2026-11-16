import { useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type {
  RecommendationOption,
  RecommendationView,
  ReplyDraftDecision,
  ReplyDraftEdit,
  ReplyDraftOfferLine,
  ReplyDraftView,
} from '../api/analysis'
import type { User } from '../api/auth'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate, formatPercent, formatPln, sourceText } from './format'
import { ACTION_KEY, STATUS } from './draftLabels'
import { OUTCOME_LABEL, RULE_LABEL } from './policyLabels'

type Decision = 'approve' | 'reject'

type Mode = Decision | 'edit' | 'supervisor-approve' | 'supervisor-reject'

type Props = {
  inquiryId: number
  // The signed-in user: a supervisor decides on drafts awaiting the supervisor.
  user: User
  // null while there is no draft for the current recommendation.
  draft: ReplyDraftView | null
  // The recommendation the draft is built from; tells why there is none and lists the options
  // the offer can be edited to.
  recommendation: RecommendationView | null
  // The policy verdict in force, placed between the chosen variant and the e-mail.
  verdict?: ReactNode
  // True when the draft's action (Regenerate, Approve, the supervisor's Approve) is the step's
  // primary one; false while another action of the step is.
  primary?: boolean
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
  // Approves or rejects, as the supervisor, the draft awaiting the supervisor read at
  // `updatedAt`, with a required reason; rejects when it failed.
  onSupervisorDecide: (updatedAt: string, action: Decision, reason: string) => Promise<void>
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Why there cannot be a (current) draft; null when the recommendation allows one.
function blockedReason(recommendation: RecommendationView | null, t: TFunction): string | null {
  if (recommendation === null) return t('draft.blocked.noRecommendation')
  if (recommendation.status === 'failed' || recommendation.choice === null) {
    return t('draft.blocked.noChoice')
  }
  if (recommendation.stale) return t('draft.blocked.recommendationStale')
  return null
}

// What the supervisor may do with a draft: nothing unless it is current and awaiting the
// supervisor; only reject a draft they passed to the supervisor themselves (four eyes).
function supervisorActions(draft: ReplyDraftView | null, user: User): Decision[] {
  if (draft === null || draft.status !== 'awaiting_supervisor' || draft.stale) return []
  if (user.role !== 'supervisor') return []
  return draft.submitted_by !== user.id ? ['approve', 'reject'] : ['reject']
}

// The decision part of the approval step: the chosen variant, the verdict in force (passed in
// as `verdict`, so the table stays where the data is), the e-mail preview and the salesperson's
// or supervisor's decision.
function ReplyDraftSection({
  inquiryId,
  user,
  draft,
  recommendation,
  verdict,
  primary = true,
  disabled,
  drafting,
  deciding,
  onRegenerate,
  onEdit,
  onDecide,
  onSupervisorDecide,
  onUnauthorized,
}: Props) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode | null>(null)
  const headingId = `draft-${inquiryId}-heading`

  async function regenerate() {
    setError(null)
    setMode(null)
    try {
      await onRegenerate()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure, t))
    }
  }

  const blocked = blockedReason(recommendation, t)
  const outdated = draft === null || draft.stale
  // A decided draft (ready to send / awaiting supervisor) is never regenerated: the backend
  // refuses it even when stale; a new recommendation replaces it instead.
  const offerRegenerate =
    blocked === null &&
    (draft === null || draft.status === 'rejected' || (draft.stale && draft.status === 'draft'))
  const canDecide = draft !== null && draft.status === 'draft' && !draft.stale
  const awaiting = draft !== null && draft.status === 'awaiting_supervisor' && !draft.stale
  const asSupervisor = supervisorActions(draft, user)
  const supervisorMode =
    mode === 'supervisor-approve' ? 'approve' : mode === 'supervisor-reject' ? 'reject' : null
  // The e-mail is the result of the reply step once the draft is ready to send.
  const showEmail = draft !== null && (draft.status !== 'ready_to_send' || draft.stale)

  return (
    <div className="grid min-w-0 gap-3">
      <section className="orchestration draft" aria-labelledby={headingId}>
        <h4 id={headingId} className="analysis__subheading">
          {t('draft.heading')}
        </h4>

        {blocked !== null && outdated && <p className="checks__line">{blocked}</p>}
        {blocked === null && draft === null && (
          <p className="checks__line">{t('draft.notGenerated')}</p>
        )}
        {draft?.stale && <p className="checks__line">{t('draft.stale')}</p>}
        {draft !== null && <DraftSummary draft={draft} />}
      </section>

      {verdict}

      {draft !== null && showEmail && <DraftEmail draft={draft} />}

      {offerRegenerate && (
        <div className="analysis__actions">
          <Button
            type="button"
            variant={primary ? 'default' : 'outline'}
            onClick={regenerate}
            disabled={disabled}
          >
            {drafting ? t('draft.drafting') : t('draft.regenerate')}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">{t('draft.regenerateFailed', { message: error })}</p>
          <Button type="button" variant="outline" onClick={regenerate} disabled={disabled}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {draft !== null && canDecide && mode === null && (
        <div className="analysis__actions" role="group" aria-label={t('draft.decisionGroup')}>
          <Button
            type="button"
            variant={primary ? 'default' : 'outline'}
            onClick={() => setMode('approve')}
            disabled={disabled}
          >
            {t('common.approve')}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setMode('edit')}
            disabled={disabled}
          >
            {t('draft.editOffer')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => setMode('reject')}
            disabled={disabled}
          >
            {t('common.reject')}
          </Button>
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

      {draft?.stale && draft.status === 'awaiting_supervisor' && (
        <p className="checks__line">{t('draft.staleAwaiting')}</p>
      )}
      {awaiting && user.role !== 'supervisor' && (
        <p className="checks__line">{t('draft.waiting')}</p>
      )}
      {awaiting && user.role === 'supervisor' && draft?.submitted_by === user.id && (
        <p className="checks__line">{t('draft.submittedBySelf')}</p>
      )}
      {draft !== null && asSupervisor.length > 0 && supervisorMode === null && (
        <div className="analysis__actions" role="group" aria-label={t('draft.supervisorGroup')}>
          {asSupervisor.includes('approve') && (
            <Button
              type="button"
              variant={primary ? 'default' : 'outline'}
              onClick={() => setMode('supervisor-approve')}
              disabled={disabled}
            >
              {t('common.approve')}
            </Button>
          )}
          <Button
            type="button"
            variant="destructive"
            onClick={() => setMode('supervisor-reject')}
            disabled={disabled}
          >
            {t('common.reject')}
          </Button>
        </div>
      )}
      {draft !== null && supervisorMode !== null && asSupervisor.includes(supervisorMode) && (
        <DecisionForm
          key={`supervisor-${supervisorMode}-${draft.updated_at}`}
          action={supervisorMode}
          supervisor
          disabled={disabled}
          saving={deciding}
          onSubmit={(reason) => onSupervisorDecide(draft.updated_at, supervisorMode, reason ?? '')}
          onDone={() => setMode(null)}
          onUnauthorized={onUnauthorized}
        />
      )}
    </div>
  )
}

// The status of the draft and the chosen variant in short: value, margin, coverage. Why this
// variant is recommended is told in the variants step only.
function DraftSummary({ draft }: { draft: ReplyDraftView }) {
  const { t } = useTranslation()
  const [statusKey, tone] = STATUS[draft.status]
  const offer = draft.offer
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="checks__outcome">
          {t('draft.statusLabel')} <span className="draft__status">{t(statusKey)}</span>
        </p>
      </div>
      <p className="analysis__meta">
        {t('draft.drafted', { date: formatDate(draft.drafted_at) })}
        {offer.edited && ` · ${t('draft.editedOffer')}`}
      </p>
      {draft.text_source === 'fallback' && <p className="draft__fallback">{t('draft.fallback')}</p>}

      <p className="analysis__meta">{t('draft.chosenVariant')}</p>
      <dl className="metrics__list">
        <dt>{t('draft.offerValue')}</dt>
        <dd>{formatPln(offer.value)}</dd>
        <dt>{t('draft.margin')}</dt>
        <dd>{formatPercent(offer.margin_percent)}</dd>
        <dt>{t('draft.coverage')}</dt>
        <dd>
          {t('common.coverage', {
            covered: offer.covered_quantity,
            requested: offer.requested_quantity,
          })}
        </dd>
      </dl>
    </>
  )
}

// A body longer than this is collapsed behind its subject.
const LONG_EMAIL = 600

// The e-mail as it would be sent: subject and body; a long body is a disclosure.
export function DraftEmail({ draft }: { draft: ReplyDraftView }) {
  const { t } = useTranslation()
  const body = (
    <pre className="draft__body" lang="pl">
      {draft.body}
    </pre>
  )
  return (
    <section className="draft__email" aria-label={t('draft.emailPreview')}>
      <p className="draft__subject">
        {t('draft.subject')} <span lang="pl">{draft.subject}</span>
      </p>
      {draft.body.length > LONG_EMAIL ? (
        <details>
          <summary className="cursor-pointer text-sm font-medium">{t('draft.showEmail')}</summary>
          <div className="mt-2">{body}</div>
        </details>
      ) : (
        body
      )}
    </section>
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
  t: TFunction,
): Promise<void> {
  setError(null)
  try {
    await props.onSubmit(value)
    props.onDone()
  } catch (failure) {
    if (failure instanceof UnauthorizedError) props.onUnauthorized()
    else setError(errorMessage(failure, t))
  }
}

// Approve with an optional comment, or reject with a required reason; the supervisor needs a
// reason for both.
function DecisionForm(
  props: FormProps<string | null> & { action: Decision; supervisor?: boolean },
) {
  const { t } = useTranslation()
  const { action, supervisor = false, disabled, saving, onDone } = props
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const approve = action === 'approve'
  const required = supervisor || !approve
  const id = supervisor ? `draft-supervisor-${action}-reason` : `draft-${action}-reason`

  function submit() {
    const text = reason.trim()
    if (required && text === '') {
      setError(
        approve ? t('draft.form.approvalReasonRequired') : t('draft.form.rejectionReasonRequired'),
      )
      return
    }
    void send(props, text === '' ? null : text, setError, t)
  }

  return (
    <form
      className="draft__form"
      noValidate
      aria-label={
        supervisor
          ? approve
            ? t('draft.form.approveSupervisor')
            : t('draft.form.rejectSupervisor')
          : approve
            ? t('draft.form.approveDraft')
            : t('draft.form.rejectDraft')
      }
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor={id}>
        {required ? t('draft.form.reasonRequired') : t('draft.form.commentOptional')}
      </label>
      <textarea
        className="resize-y"
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
        <Button type="submit" disabled={disabled}>
          {saving
            ? t('common.saving')
            : approve
              ? t('draft.form.confirmApproval')
              : t('draft.form.confirmRejection')}
        </Button>
        <Button type="button" variant="outline" onClick={onDone} disabled={saving}>
          {t('common.cancel')}
        </Button>
      </div>
    </form>
  )
}

type LineDraft = { quantity: string; unit_price: string }

function lineDrafts(lines: { quantity: number; unit_price: string }[]): LineDraft[] {
  return lines.map((line) => ({
    quantity: String(line.quantity),
    unit_price: line.unit_price,
  }))
}

type EditProps = FormProps<ReplyDraftEdit> & {
  draft: ReplyDraftView
  // The recommendation's options; the offer can be edited to any of them.
  options: RecommendationOption[]
}

// Another option, quantities and unit prices of its lines, and a required reason. Range
// checks (quantity ≥ 1, price above zero) stay with the API, whose 422 message is shown here.
function EditForm(props: EditProps) {
  const { t } = useTranslation()
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
  // The current offer leads when the recommendation no longer lists its option.
  const choices: Pick<RecommendationOption, 'id' | 'kind' | 'value'>[] = options.some(
    (item) => item.id === offer.option_id,
  )
    ? options
    : [{ id: offer.option_id, kind: offer.kind, value: offer.value }, ...options]

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
        setError(t('draft.form.quantityWhole'))
        return
      }
      if (!/^\d+(\.\d{1,2})?$/.test(price)) {
        setError(t('draft.form.unitPriceInvalid'))
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
      setError(t('draft.form.editReasonRequired'))
      return
    }
    void send(props, { option_id: optionId, lines: built, reason: text }, setError, t)
  }

  const id = (name: string) => `draft-edit-${name}`

  return (
    <form
      className="draft__form"
      noValidate
      aria-label={t('draft.editOffer')}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor={id('option')}>{t('draft.form.option')}</label>
      <select id={id('option')} value={optionId} onChange={(event) => choose(event.target.value)}>
        {choices.map((item) => (
          <option key={item.id} value={item.id}>
            {t('draft.optionLabel', {
              kind: t(`optionKind.${item.kind}`),
              value: formatPln(item.value),
            })}
          </option>
        ))}
      </select>

      <div className="policy__table-wrap">
        <table className="policy__table draft__lines">
          <caption className="orchestration__stage-title">{t('draft.form.offerLines')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('draft.form.product')}</th>
              <th scope="col">{t('draft.form.quantity')}</th>
              <th scope="col">{t('draft.form.unitPrice')}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((line, index) => {
              const name = `${line.product_code}, ${sourceText(line, t)}`
              return (
                <tr key={`${line.source}-${line.product_code}-${index}`}>
                  <th scope="row">
                    {line.product_code} <span className="muted">· {sourceText(line, t)}</span>
                    {'list_price' in line && (
                      <span className="draft__list-price">
                        {t('draft.form.listPrice', {
                          price: formatPln(line.list_price),
                        })}
                      </span>
                    )}
                  </th>
                  <td>
                    <input
                      aria-label={t('draft.form.quantityOf', { name })}
                      inputMode="numeric"
                      value={lines[index]?.quantity ?? ''}
                      onChange={(event) => update(index, 'quantity', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={t('draft.form.unitPriceOf', { name })}
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

      <label htmlFor={id('reason')}>{t('draft.form.reasonRequired')}</label>
      <textarea
        className="resize-y"
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
        <Button type="submit" disabled={disabled}>
          {saving ? t('common.saving') : t('draft.form.saveEdit')}
        </Button>
        <Button type="button" variant="outline" onClick={onDone} disabled={saving}>
          {t('common.cancel')}
        </Button>
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
  const { t } = useTranslation()
  const headingId = `decisions-${inquiryId}-heading`
  return (
    <section className="orchestration draft__history" aria-labelledby={headingId}>
      <details>
        <summary className="cursor-pointer">
          <h4 id={headingId} className="analysis__subheading inline">
            {t('decisionHistory.heading')}
          </h4>
        </summary>
        <ol className="checks__list mt-2">
          {decisions.map((decision, index) => {
            const [statusKey, tone] = STATUS[decision.status_after]
            const snapshot = decision.snapshot
            const outcome = snapshot?.policy_outcome ?? null
            const failing = snapshot?.failing_rules.map((code) => t(RULE_LABEL[code])) ?? []
            // Older snapshots lack the rules the verdict could not evaluate.
            const notEvaluated = (snapshot?.not_evaluated_rules ?? []).map((code) =>
              t(RULE_LABEL[code]),
            )
            const rules = [
              ...(failing.length > 0
                ? [t('decisionHistory.failing', { rules: failing.join(', ') })]
                : []),
              ...(notEvaluated.length > 0
                ? [
                    t('decisionHistory.notEvaluated', {
                      rules: notEvaluated.join(', '),
                    }),
                  ]
                : []),
            ]
            return (
              <li key={`${decision.decided_at}-${index}`} className="check">
                <p className="check__head">
                  <span className="check__name">
                    {t(ACTION_KEY[decision.action])}
                    {!decision.current && (
                      <span className="draft__earlier">{t('decisionHistory.earlier')}</span>
                    )}
                  </span>
                  <span className={`check__status check__status--${tone}`}>{t(statusKey)}</span>
                </p>
                <dl className="metrics__list">
                  <dt>{t('decisionHistory.by')}</dt>
                  <dd>{decision.decided_by_name ?? t('decisionHistory.unknownUser')}</dd>
                  <dt>{t('decisionHistory.when')}</dt>
                  <dd>{formatDate(decision.decided_at)}</dd>
                  <dt>{t('decisionHistory.reason')}</dt>
                  <dd>{decision.reason ?? '—'}</dd>
                  <dt>{t('decisionHistory.offer')}</dt>
                  <dd>
                    {snapshot === null
                      ? t('decisionHistory.unavailable')
                      : formatPln(snapshot.offer.value)}
                  </dd>
                  <dt>{t('decisionHistory.policy')}</dt>
                  <dd>
                    {snapshot === null
                      ? t('decisionHistory.unavailable')
                      : outcome === null
                        ? t('decisionHistory.noVerdict')
                        : t(OUTCOME_LABEL[outcome].key)}
                    {rules.length > 0 && ` (${rules.join('; ')})`}
                  </dd>
                </dl>
              </li>
            )
          })}
        </ol>
      </details>
    </section>
  )
}

export default ReplyDraftSection
