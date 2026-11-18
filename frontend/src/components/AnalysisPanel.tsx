import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { Link, useMatch, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import {
  analyzeInquiry,
  decideAsSupervisor,
  decideDraft,
  editDraft,
  fetchAnalysis,
  regenerateDraft,
  rerunChecks,
  rerunOrchestration,
  rerunPolicy,
  rerunRecommendation,
  saveCorrections,
  type Analysis,
  type FieldName,
  type Outcome,
  type ParsedFields,
  type PriceKind,
  type ReplyDraftEdit,
  type ReplyDraftStatus,
} from '../api/analysis'
import type { User } from '../api/auth'
import { ApiError, UnauthorizedError } from '../api/client'
import { describeError, localError, type ErrorDescriptor } from '../api/errorMessages'
import { Button } from '@/components/ui/button'
import ChecksSection from './ChecksSection'
import { errorMessage, formatDate } from './format'
import { inquirySteps, stepBackReason, type StepBackKey, type StepId } from './inquirySteps'
import InquiryStepper from './InquiryStepper'
import type { InquiryStatusFacts } from './inquiryStatus'
import OrchestrationSection from './OrchestrationSection'
import PolicySection from './PolicySection'
import { policyRerunOffered } from './policyLabels'
import RecommendationSection from './RecommendationSection'
import ReplyDraftSection, { DecisionHistory } from './ReplyDraftSection'
import ReplyStep from './ReplyStep'
import RunInspector from './RunInspector'

type Props = {
  inquiryId: number
  // The e-mail text: shown in the inquiry step, as a disclosure in the others.
  body: string
  // Raw status from the inquiry summary; this remains reliable if a draft cannot be decoded.
  awaitingSupervisor?: boolean
  // The signed-in user: a supervisor decides on drafts awaiting the supervisor.
  user: User
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
  // Called with the facts behind the inquiry's status (an analysis exists, the current
  // outcome, the draft's status) whenever the analysis is loaded or replaced, so the inbox can
  // update its badges and filter.
  onStatusFacts?: (inquiryId: number, facts: InquiryStatusFacts) => void
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; analysis: Analysis | null }
  | { kind: 'error'; error: ErrorDescriptor }

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

const PRICE_KIND_KEY = {
  none: 'analysis.priceKind.none',
  best_price: 'analysis.priceKind.best_price',
  discount_percent: 'analysis.priceKind.discount_percent',
  target_price: 'analysis.priceKind.target_price',
} as const satisfies Record<PriceKind, string>

const VALUED_PRICE_KINDS: readonly PriceKind[] = ['discount_percent', 'target_price']

const SUBSTITUTE_KEY = {
  yes: 'analysis.substitute.yes',
  no: 'analysis.substitute.no',
  unknown: 'analysis.substitute.unknown',
} as const satisfies Record<Substitute, string>

// Notices are kept as keys and translated at render time, so they follow a language switch.
type NoticeKey =
  | 'analysis.saved'
  | 'analysis.reloaded'
  | 'analysis.draftReloaded'
  | 'decision.sentToSupervisor'
  | 'decision.approved'
  | 'decision.edited'
  | 'decision.supervisorApproved'

// The draft was written since it was read (another decision, a regenerated draft or a new
// recommendation); every other 409 of a decision is shown at its form.
function draftChanged(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && error.code === 'DRAFT_CHANGED'
}

// As the inbox lists it: the outcome only while the result matches the current analysis.
function outcomeOf(analysis: Analysis | null): Outcome | null {
  const checks = analysis?.checks ?? null
  return checks === null || checks.stale ? null : checks.outcome
}

// As the inbox lists it: the stored draft's status, also of a stale draft.
function draftStatusOf(analysis: Analysis | null): ReplyDraftStatus | null {
  return analysis?.draft?.status ?? null
}

// The facts of the inquiry's status, as the inbox lists them.
function statusFactsOf(analysis: Analysis | null): InquiryStatusFacts {
  return {
    analyzed: analysis !== null,
    outcome: outcomeOf(analysis),
    draft_status: draftStatusOf(analysis),
  }
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
): { fields: ParsedFields } | { error: ErrorDescriptor } {
  const quantity = draft.quantity.trim()
  if (quantity !== '' && !/^\d+$/.test(quantity)) {
    return { error: localError('analysis.error.quantityWhole') }
  }
  let priceValue: string | null = null
  if (VALUED_PRICE_KINDS.includes(draft.price_kind)) {
    priceValue = draft.price_value.trim().replace(',', '.')
    if (priceValue === '') return { error: localError('analysis.error.priceValueRequired') }
    if (!/^\d+(\.\d+)?$/.test(priceValue)) return { error: localError('analysis.error.priceValueNumber') }
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

function emptyOr(value: string | null, t: TFunction): string {
  return value === null || value === '' ? t('analysis.empty') : value
}

function formatPrice(kind: PriceKind, value: string | null, t: TFunction): string {
  if (kind === 'discount_percent' && value !== null) return t('analysis.discountValue', { value })
  if (kind === 'target_price' && value !== null) return t('analysis.targetValue', { value })
  return t(PRICE_KIND_KEY[kind])
}

// How the original (parsed) value of a field reads next to the "edited" mark.
function modelValue(field: FieldName, fields: ParsedFields, t: TFunction): string {
  switch (field) {
    case 'customer':
      return emptyOr(fields.customer, t)
    case 'product_code':
      return emptyOr(fields.product_code, t)
    case 'quantity':
      return fields.quantity === null ? t('analysis.empty') : String(fields.quantity)
    case 'deadline':
      return emptyOr(fields.deadline, t)
    case 'substitute_allowed':
      return t(SUBSTITUTE_KEY[substituteOf(fields.substitute_allowed)])
    case 'price':
      return formatPrice(fields.price_kind, fields.price_value, t)
  }
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
  const { t } = useTranslation()
  const reason = analysis.uncertain[name]
  const edited = analysis.corrected_fields.includes(name)
  return (
    <div className={reason === undefined ? 'field' : 'field field--uncertain'}>
      <div className="field__label">
        <label htmlFor={inputId}>{label}</label>
        {edited && (
          <span className="field__edited">
            {t('analysisFields.editedOriginally', {
              value: modelValue(name, analysis.model_fields, t),
            })}
          </span>
        )}
      </div>
      {children}
      {reason !== undefined && (
        <div className="field__uncertain">
          <p className="field__reason">{t('analysis.uncertain', { reason })}</p>
          <label className="field__check">
            <input
              type="checkbox"
              className="m-1"
              checked={reviewed.includes(name)}
              onChange={(event) => onReviewed(name, event.target.checked)}
            />
            {t('analysis.looksRight')}
          </label>
        </div>
      )}
    </div>
  )
}

// Why the flow moved back to an earlier step: announced next to the notice, in one status.
type StepMessage = { step: StepId; reason: StepBackKey }

function MailBody({ body }: { body: string }) {
  return <div className="text-sm wrap-anywhere whitespace-pre-wrap">{body}</div>
}

function AnalysisPanel({ inquiryId, body, awaitingSupervisor = false, user, onUnauthorized, onStatusFacts }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  // The run inspector is open while /inquiries/$inquiryId/run matches; it reads the analysis
  // this panel holds, so it never refetches.
  const inspecting = useMatch({
    from: '/inbox/inquiries/$inquiryId/run',
    shouldThrow: false,
  })
  const inspectorLink = useRef<HTMLAnchorElement>(null)
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [reviewed, setReviewed] = useState<FieldName[]>([])
  const [busy, setBusy] = useState<
    | 'analyzing'
    | 'saving'
    | 'checking'
    | 'orchestrating'
    | 'recommending'
    | 'evaluating'
    | 'drafting'
    | 'deciding'
    | null
  >(null)
  const [analyzeError, setAnalyzeError] = useState<ErrorDescriptor | null>(null)
  const [formError, setFormError] = useState<ErrorDescriptor | null>(null)
  const [notice, setNotice] = useState<NoticeKey | null>(null)
  const [confirming, setConfirming] = useState(false)
  // The step whose panel is shown; it follows the active step unless the user opens a done one.
  const [viewed, setViewed] = useState<StepId>('inquiry')
  const [stepMessage, setStepMessage] = useState<StepMessage | null>(null)
  // The analysis last shown, to tell where the flow moved when the next one arrives.
  const lastAnalysis = useRef<Analysis | null>(null)

  // Moving forward selects the new active step; moving back selects it and says why.
  const follow = useCallback((next: Analysis | null) => {
    const prev = lastAnalysis.current
    lastAnalysis.current = next
    const before = inquirySteps(prev).active
    const after = inquirySteps(next).active
    const reason = stepBackReason(prev, next)
    if (reason !== null) {
      setStepMessage({ step: after, reason })
      setViewed(after)
    } else {
      setStepMessage(null)
      if (after !== before) setViewed(after)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchAnalysis(inquiryId, controller.signal).then(
      (analysis) => {
        setLoad({ kind: 'ok', analysis })
        setDraft(analysis === null ? null : toDraft(analysis.fields))
        setReviewed([])
        follow(analysis)
        onStatusFacts?.(inquiryId, statusFactsOf(analysis))
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onUnauthorized()
        else {
          const descriptor = describeError(error)
          if (descriptor !== null) setLoad({ kind: 'error', error: descriptor })
        }
      },
    )
    return () => controller.abort()
  }, [inquiryId, loadAttempt, onUnauthorized, onStatusFacts, follow])

  function show(analysis: Analysis) {
    setLoad({ kind: 'ok', analysis })
    setDraft(toDraft(analysis.fields))
    setReviewed([])
    follow(analysis)
    onStatusFacts?.(inquiryId, statusFactsOf(analysis))
  }

  function reload() {
    setLoad({ kind: 'loading' })
    setLoadAttempt((n) => n + 1)
  }

  const analysis = load.kind === 'ok' ? load.analysis : null
  const dirty = analysis !== null && draft !== null && !sameDraft(draft, toDraft(analysis.fields))
  const hasCorrections =
    analysis !== null && (analysis.corrected_at !== null || analysis.corrected_fields.length > 0)

  // A re-run of the checks leaves the fields as they were, so unsaved edits are kept
  // unless the analysis itself was replaced or corrected meanwhile.
  function showChecked(next: Analysis) {
    if (
      analysis === null ||
      next.analyzed_at !== analysis.analyzed_at ||
      next.corrected_at !== analysis.corrected_at
    ) {
      show(next)
      return
    }
    setLoad({ kind: 'ok', analysis: next })
    follow(next)
    onStatusFacts?.(inquiryId, statusFactsOf(next))
  }

  // Errors are left to ChecksSection, which shows them next to its button.
  async function rerun() {
    setBusy('checking')
    try {
      showChecked(await rerunChecks(inquiryId))
    } finally {
      setBusy(null)
    }
  }

  // Errors are left to OrchestrationSection, which shows them next to its button.
  async function rerunOrchestrator() {
    setBusy('orchestrating')
    try {
      showChecked(await rerunOrchestration(inquiryId))
    } finally {
      setBusy(null)
    }
  }

  // Errors are left to RecommendationSection, which shows them next to its button.
  async function rerunRecommender() {
    setBusy('recommending')
    try {
      showChecked(await rerunRecommendation(inquiryId))
    } finally {
      setBusy(null)
    }
  }

  // Errors are left to PolicySection, which shows them next to its button.
  async function reevaluatePolicy() {
    setBusy('evaluating')
    try {
      showChecked(await rerunPolicy(inquiryId))
    } finally {
      setBusy(null)
    }
  }

  // Errors are left to ReplyDraftSection, which shows them next to its button.
  async function regenerateReplyDraft() {
    setBusy('drafting')
    try {
      showChecked(await regenerateDraft(inquiryId))
    } finally {
      setBusy(null)
    }
  }

  // A draft written meanwhile reloads the analysis, like a replaced analysis on save; other
  // errors are left to ReplyDraftSection, which shows them at its form.
  // After a decision the notice says what happened, unless the step-back message already
  // announces the transition (a rejection).
  async function decideOnReplyDraft(
    send: () => Promise<Analysis>,
    noticeFor: (next: Analysis) => NoticeKey | null,
  ) {
    setBusy('deciding')
    setNotice(null)
    try {
      const next = await send()
      const announced = stepBackReason(lastAnalysis.current, next) !== null
      showChecked(next)
      if (!announced) setNotice(noticeFor(next))
    } catch (error) {
      if (!draftChanged(error)) throw error
      setNotice('analysis.draftReloaded')
      reload()
    } finally {
      setBusy(null)
    }
  }

  function editReplyDraft(updatedAt: string, edit: ReplyDraftEdit) {
    return decideOnReplyDraft(
      () => editDraft(inquiryId, updatedAt, edit),
      () => 'decision.edited',
    )
  }

  function decideReplyDraft(
    updatedAt: string,
    action: 'approve' | 'reject',
    reason: string | null,
  ) {
    return decideOnReplyDraft(
      () => decideDraft(inquiryId, updatedAt, action, reason),
      (next) => {
        if (action !== 'approve') return null
        const status = next.draft?.status
        if (status === 'awaiting_supervisor') return 'decision.sentToSupervisor'
        return status === 'ready_to_send' ? 'decision.approved' : null
      },
    )
  }

  function decideReplyDraftAsSupervisor(
    updatedAt: string,
    action: 'approve' | 'reject',
    reason: string,
  ) {
    return decideOnReplyDraft(
      () => decideAsSupervisor(inquiryId, updatedAt, action, reason),
      (next) =>
        action === 'approve' && next.draft?.status === 'ready_to_send'
          ? 'decision.supervisorApproved'
          : null,
    )
  }

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
      else setAnalyzeError(describeError(error, 'write'))
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
      setNotice('analysis.saved')
    } catch (error) {
      if (error instanceof UnauthorizedError) onUnauthorized()
      else if (error instanceof ApiError && error.status === 409) {
        setNotice('analysis.reloaded')
        setFormError(describeError(error, 'write'))
        reload()
      } else setFormError(describeError(error, 'write'))
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

  function showStep(step: StepId) {
    setViewed(step)
    setStepMessage(null)
  }

  const id = (name: string) => `analysis-${inquiryId}-${name}`

  // The corrections form and the check results: the inquiry step.
  function renderFormAndChecks(analysis: Analysis, draft: Draft) {
    const fieldProps = { analysis, reviewed, onReviewed: setFieldReviewed }
    // One primary action: saving first, then the stale checks, then moving on to Variants;
    // a standard inquiry has none.
    const unsaved = dirty || reviewed.length > 0
    const checks = analysis.checks
    const checksCurrent = checks !== null && !checks.stale
    const checksPrimary = !unsaved && !checksCurrent
    const nextToVariants = checksCurrent && checks.outcome === 'exception'
    const nextPrimary = !unsaved && nextToVariants
    return (
      <>
        <p className="analysis__meta">
          {analysis.analyzed_by_name
            ? t('analysis.meta.analyzedBy', {
                date: formatDate(analysis.analyzed_at),
                name: analysis.analyzed_by_name,
              })
            : t('analysis.meta.analyzed', {
                date: formatDate(analysis.analyzed_at),
              })}
          {analysis.corrected_at && (
            <>
              {' · '}
              {analysis.corrected_by_name
                ? t('analysis.meta.correctedBy', {
                    date: formatDate(analysis.corrected_at),
                    name: analysis.corrected_by_name,
                  })
                : t('analysis.meta.corrected', {
                    date: formatDate(analysis.corrected_at),
                  })}
            </>
          )}
        </p>

        <form
          id={id('form')}
          className="analysis__form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <Field
            name="customer"
            label={t('analysis.field.customer')}
            inputId={id('customer')}
            {...fieldProps}
          >
            <input
              id={id('customer')}
              value={draft.customer}
              onChange={(event) => update('customer', event.target.value)}
            />
          </Field>
          <Field
            name="product_code"
            label={t('analysis.field.product')}
            inputId={id('product')}
            {...fieldProps}
          >
            <input
              id={id('product')}
              value={draft.product_code}
              onChange={(event) => update('product_code', event.target.value)}
            />
          </Field>
          <Field
            name="quantity"
            label={t('analysis.field.quantity')}
            inputId={id('quantity')}
            {...fieldProps}
          >
            <input
              id={id('quantity')}
              inputMode="numeric"
              value={draft.quantity}
              onChange={(event) => update('quantity', event.target.value)}
            />
          </Field>
          <Field
            name="deadline"
            label={t('analysis.field.deadline')}
            inputId={id('deadline')}
            {...fieldProps}
          >
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
            label={t('analysis.field.substituteAllowed')}
            inputId={id('substitute')}
            {...fieldProps}
          >
            <select
              id={id('substitute')}
              value={draft.substitute}
              onChange={(event) => update('substitute', event.target.value as Substitute)}
            >
              {(Object.keys(SUBSTITUTE_KEY) as Substitute[]).map((value) => (
                <option key={value} value={value}>
                  {t(SUBSTITUTE_KEY[value])}
                </option>
              ))}
            </select>
          </Field>
          <Field
            name="price"
            label={t('analysis.field.priceExpectation')}
            inputId={id('price-kind')}
            {...fieldProps}
          >
            <div className="field__row">
              <select
                id={id('price-kind')}
                value={draft.price_kind}
                onChange={(event) => update('price_kind', event.target.value as PriceKind)}
              >
                {(Object.keys(PRICE_KIND_KEY) as PriceKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {t(PRICE_KIND_KEY[kind])}
                  </option>
                ))}
              </select>
              {VALUED_PRICE_KINDS.includes(draft.price_kind) && (
                <input
                  aria-label={
                    draft.price_kind === 'discount_percent'
                      ? t('analysis.priceValueLabel.discount_percent')
                      : t('analysis.priceValueLabel.target_price')
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
        </form>

        <ChecksSection
          inquiryId={inquiryId}
          analysis={analysis}
          disabled={busy !== null}
          running={busy === 'checking'}
          onRerun={rerun}
          primary={checksPrimary}
          onUnauthorized={onUnauthorized}
        />

        <div role="group" aria-label={t('steps.actions')} className="sticky bottom-0 z-10 border-t border-border bg-background py-3 grid gap-2">
          {formError && (
            <p className="error" role="alert">
              {errorMessage(formError, t)}
            </p>
          )}
          <div className="analysis__actions">
            <Button
              type="submit"
              form={id('form')}
              variant={unsaved ? 'default' : 'outline'}
              disabled={busy !== null || !unsaved}
            >
              {busy === 'saving' ? t('common.saving') : t('analysis.save')}
            </Button>
            {nextToVariants && (
              <Button
                type="button"
                variant={nextPrimary ? 'default' : 'outline'}
                onClick={() => showStep('variants')}
                disabled={busy !== null}
              >
                {t('steps.nextVariants')}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              onClick={requestReanalysis}
              disabled={busy !== null}
            >
              {busy === 'analyzing' ? t('analysis.analyzing') : t('analysis.reanalyze')}
            </Button>
          </div>
          {confirming && (
            <div className="analysis__confirm">
              <p>{t('analysis.correctionsLost')}</p>
              <div className="analysis__actions">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={runAnalysis}
                  disabled={busy !== null}
                >
                  {t('analysis.reanalyzeAnyway')}
                </Button>
                <Button type="button" variant="outline" onClick={() => setConfirming(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </>
    )
  }

  function renderPanels(analysis: Analysis, draft: Draft, steps: ReturnType<typeof inquirySteps>) {
    const exception = analysis.checks !== null && analysis.checks.outcome === 'exception'
    // The orchestrator's re-run is offered (and primary) until it has a current, complete result.
    const orchestration = analysis.orchestration
    const orchestrationRerun =
      orchestration === null || orchestration.stale || orchestration.status !== 'completed'
    const decisions = analysis.decisions ?? []
    // Outside the exception: decisions stay visible after a correction removes it.
    const historyInInquiry =
      decisions.length > 0 && steps.states.approval !== 'done' && steps.states.approval !== 'active'
    const mail = (
      <details className="rounded-md border bg-card px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium">{t('steps.showMail')}</summary>
        <div className="mt-2">
          <MailBody body={body} />
        </div>
      </details>
    )
    // One primary action in the approval step: re-running the policy comes before the draft's.
    const policyRerun = policyRerunOffered(analysis.policy ?? null, analysis.recommendation ?? null)
    const replyDraft = (
      <ReplyDraftSection
        inquiryId={inquiryId}
        user={user}
        draft={analysis.draft ?? null}
        recommendation={analysis.recommendation ?? null}
        verdict={
          <PolicySection
            inquiryId={inquiryId}
            policy={analysis.policy ?? null}
            recommendation={analysis.recommendation ?? null}
            draft={analysis.draft ?? null}
            primary={policyRerun}
            disabled={busy !== null}
            running={busy === 'evaluating'}
            onRerun={reevaluatePolicy}
            onUnauthorized={onUnauthorized}
          />
        }
        primary={!policyRerun}
        disabled={busy !== null}
        drafting={busy === 'drafting'}
        deciding={busy === 'deciding'}
        onRegenerate={regenerateReplyDraft}
        onEdit={editReplyDraft}
        onDecide={decideReplyDraft}
        onSupervisorDecide={decideReplyDraftAsSupervisor}
        onUnauthorized={onUnauthorized}
      />
    )
    return {
      inquiry: (
        <>
          <section aria-label={t('steps.mail')}>
            <MailBody body={body} />
          </section>
          {renderFormAndChecks(analysis, draft)}
          {historyInInquiry && <DecisionHistory inquiryId={inquiryId} decisions={decisions} />}
        </>
      ),
      variants: (
        <>
          {mail}
          {exception && (
            <RecommendationSection
              inquiryId={inquiryId}
              recommendation={analysis.recommendation ?? null}
              orchestration={analysis.orchestration}
              disabled={busy !== null}
              running={busy === 'recommending'}
              onRerun={rerunRecommender}
              primary={!orchestrationRerun}
              onUnauthorized={onUnauthorized}
              expectedDeadline={analysis.fields.deadline}
            />
          )}
          {exception && (
            <details open={orchestrationRerun} className="rounded-md border bg-card px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium">
                {t('steps.findings')}
              </summary>
              <div className="mt-2">
                <OrchestrationSection
                  inquiryId={inquiryId}
                  orchestration={analysis.orchestration}
                  disabled={busy !== null}
                  running={busy === 'orchestrating'}
                  onRerun={rerunOrchestrator}
                  primary={orchestrationRerun}
                  onUnauthorized={onUnauthorized}
                />
              </div>
            </details>
          )}
          {exception && !orchestrationRerun && steps.states.variants === 'done' && (
            <div role="group" aria-label={t('steps.actions')} className="sticky bottom-0 z-10 border-t border-border bg-background py-3 analysis__actions">
              <Button type="button" onClick={() => showStep('approval')} disabled={busy !== null}>
                {t('steps.nextApproval')}
              </Button>
            </div>
          )}
        </>
      ),
      approval: (
        <>
          {mail}
          {exception && replyDraft}
          {decisions.length > 0 && <DecisionHistory inquiryId={inquiryId} decisions={decisions} />}
        </>
      ),
      reply: (
        <>
          {exception && (
            <ReplyStep inquiryId={inquiryId} draft={analysis.draft ?? null} decisions={decisions} />
          )}
          {mail}
        </>
      ),
    } satisfies Record<StepId, ReactNode>
  }

  function renderSteps() {
    const steps = inquirySteps(analysis)
    // A locked or not needed step cannot be viewed; the active step stands in for it.
    const state = steps.states[viewed]
    const shown = state === 'locked' || state === 'not_needed' ? steps.active : viewed
    const panels =
      analysis !== null && draft !== null
        ? renderPanels(analysis, draft, steps)
        : {
            inquiry: (
              <>
                <section aria-label={t('steps.mail')}>
                  <MailBody body={body} />
                </section>
                <div className="analysis__actions">
                  <Button type="button" onClick={runAnalysis} disabled={busy !== null}>
                    {busy === 'analyzing' ? t('analysis.analyzing') : t('analysis.analyze')}
                  </Button>
                </div>
              </>
            ),
            variants: null,
            approval: null,
            reply: null,
          }
    return <InquiryStepper steps={steps} viewed={shown} onView={showStep} panels={panels} />
  }

  return (
    <section className="analysis" aria-labelledby={id('heading')}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 id={id('heading')} className="analysis__heading font-bold">
          {t('analysis.heading')}
        </h3>
        {analysis !== null && (
          <Link
            ref={inspectorLink}
            to="/inquiries/$inquiryId/run"
            params={{ inquiryId: String(inquiryId) }}
            className="text-sm text-primary underline underline-offset-4"
          >
            {t('inspector.open')}
          </Link>
        )}
      </div>

      {awaitingSupervisor && (
        <aside className="grid gap-2 rounded-md border border-warning bg-warning/10 p-3">
          <p>{t('supervisor.lock.waiting')}</p>
          {user.role === 'supervisor' && (
            <Link
              to="/approvals/$inquiryId"
              params={{ inquiryId: String(inquiryId) }}
              className="w-fit text-primary underline underline-offset-4"
            >
              {t('supervisor.lock.openReview')}
            </Link>
          )}
        </aside>
      )}
      {/* Always mounted, so a message that is set later is announced; empty it takes no room. */}
      <div className="analysis__notice empty:sr-only" role="status">
        {notice && <p>{t(notice)}</p>}
        {stepMessage && (
          <p>
            {t('steps.backMessage', {
              step: t(`steps.names.${stepMessage.step}`),
              reason: t(stepMessage.reason),
            })}
          </p>
        )}
      </div>
      <fieldset disabled={awaitingSupervisor} className="grid min-w-0 gap-3 border-0 p-0">
        {load.kind === 'loading' && <p className="muted">{t('analysis.loading')}</p>}
        {load.kind === 'error' && (
          <div role="alert" className="analysis__problem">
            <p className="error">{errorMessage(load.error, t)}</p>
            <Button type="button" variant="outline" onClick={reload}>
              {t('common.retry')}
            </Button>
          </div>
        )}
        {analyzeError && (
          <div role="alert" className="analysis__problem">
            <p className="error">{errorMessage(analyzeError, t)}</p>
            <Button
              type="button"
              variant="outline"
              onClick={requestReanalysis}
              disabled={busy !== null}
            >
              {t('common.retry')}
            </Button>
          </div>
        )}
        {load.kind === 'ok' && renderSteps()}
      </fieldset>

      <RunInspector
        analysis={analysis}
        loading={load.kind === 'loading'}
        loadError={load.kind === 'error' ? load.error : null}
        onRetry={reload}
        open={inspecting !== undefined}
        onClose={() =>
          void navigate({
            to: '/inquiries/$inquiryId',
            params: { inquiryId: String(inquiryId) },
          })
        }
        returnFocusTo={inspectorLink}
      />
    </section>
  )
}

export default AnalysisPanel
