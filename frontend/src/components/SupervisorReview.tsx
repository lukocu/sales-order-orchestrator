import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { ApiError, UnauthorizedError } from '../api/client'
import { describeError, localError, type ErrorDescriptor } from '../api/errorMessages'
import { fetchAnalysis } from '../api/analysis'
import { decideAsSupervisor, type Analysis, type ReplyDraftStatus } from '../api/analysis'
import { fetchSupervisorReview, type SupervisorReview as ReviewData } from '../api/supervisor'
import { useSession } from '../session'
import { useSupervisorQueue } from '../useSupervisorQueue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { errorMessage, formatDate, formatPercent, formatPln, sourceText } from './format'
import { RULE_LABEL, VERDICT_LABEL } from './policyLabels'
import { policyReason } from './businessMessages'
import { DecisionHistory } from './ReplyDraftSection'
import RunInspector from './RunInspector'

type Props = { inquiryId: number; inspectorOpen?: boolean }
type LoadState =
  | { key: string; kind: 'loading' }
  | { key: string; kind: 'ready'; data: ReviewData }
  | { key: string; kind: 'error'; error: ErrorDescriptor }
type Decision = 'approve' | 'reject'

function SupervisorReview({ inquiryId, inspectorOpen = false }: Props) {
  const { t } = useTranslation()
  const { onUnauthorized } = useSession()
  const { refresh, remove } = useSupervisorQueue()
  const navigate = useNavigate()
  const [state, setState] = useState<LoadState>({ key: '', kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const loadKey = `${inquiryId}:${attempt}`
  const visibleState: LoadState = state.key === loadKey ? state : { key: loadKey, kind: 'loading' }
  const [action, setAction] = useState<Decision | null>(null)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<ErrorDescriptor | null>(null)
  const [refreshError, setRefreshError] = useState<ErrorDescriptor | null>(null)
  const [inspectorError, setInspectorError] = useState<ErrorDescriptor | null>(null)
  const [requiresReview, setRequiresReview] = useState(false)
  const [decided, setDecided] = useState(false)
  const [inspectorResult, setInspectorResult] = useState<{
    inquiryId: number
    analysis: Analysis | null
  } | null>(null)
  const [inspectorAttempt, setInspectorAttempt] = useState(0)
  const analysis = inspectorResult?.inquiryId === inquiryId ? inspectorResult.analysis : null
  const analysisLoading = inspectorOpen && inspectorResult?.inquiryId !== inquiryId
  const inspectorTrigger = useRef<HTMLButtonElement>(null)
  const resultHeading = useRef<HTMLHeadingElement>(null)

  const load = useCallback(
    (key: string, signal?: AbortSignal) => fetchSupervisorReview(inquiryId, signal).then((data) => {
      setState({ key, kind: 'ready', data })
      return data
    }),
    [inquiryId],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(loadKey, controller.signal).catch((error: unknown) => {
      if (controller.signal.aborted) return
      if (error instanceof UnauthorizedError) onUnauthorized()
      else {
        const descriptor = describeError(error)
        if (descriptor !== null) setState({ key: loadKey, kind: 'error', error: descriptor })
      }
    })
    return () => controller.abort()
  }, [load, loadKey, onUnauthorized])

  useEffect(() => {
    if (!inspectorOpen) return
    let active = true
    const controller = new AbortController()
    fetchAnalysis(inquiryId, controller.signal).then(
      (value) => { if (active) setInspectorResult({ inquiryId, analysis: value }) },
      (error: unknown) => {
        if (!active) return
        if (error instanceof UnauthorizedError) onUnauthorized()
        else {
          setInspectorError(describeError(error))
          setInspectorResult({ inquiryId, analysis: null })
        }
      },
    )
    return () => { active = false; controller.abort() }
  }, [inquiryId, inspectorOpen, inspectorAttempt, onUnauthorized])

  // Focus the result only after a decision made in this view, not on a plain visit to a decided case.
  useLayoutEffect(() => {
    if (decided) resultHeading.current?.focus()
  }, [decided])

  // Coming back to the tab re-reads the review, so a decision is never sent on a stale token.
  const currentToken = visibleState.kind === 'ready' ? visibleState.data.draft_updated_at : null
  const tokenRef = useRef<string | null>(null)
  useEffect(() => {
    tokenRef.current = currentToken
  }, [currentToken])
  useEffect(() => {
    let controller: AbortController | null = null
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      controller?.abort()
      const own = new AbortController()
      controller = own
      fetchSupervisorReview(inquiryId, own.signal).then(
        (latest) => {
          if (own.signal.aborted) return
          if (tokenRef.current !== null && latest.draft_updated_at !== tokenRef.current) setRequiresReview(true)
          setAction((current) => (current !== null && latest.allowed_actions.includes(current) ? current : null))
          setState((current) => (current.key === loadKey && current.kind === 'ready' ? { key: loadKey, kind: 'ready', data: latest } : current))
        },
        (error: unknown) => {
          if (own.signal.aborted) return
          if (error instanceof UnauthorizedError) onUnauthorized()
        },
      )
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      document.removeEventListener('visibilitychange', onVisible)
      controller?.abort()
    }
  }, [inquiryId, loadKey, onUnauthorized])

  async function submitDecision() {
    if (visibleState.kind !== 'ready' || action === null || visibleState.data.draft_updated_at === null || !visibleState.data.allowed_actions.includes(action)) return
    if (!reason.trim()) {
      setActionError(localError('supervisor.review.reasonRequired'))
      return
    }
    setSaving(true)
    setActionError(null)
    setRefreshError(null)
    try {
      const updated = await decideAsSupervisor(inquiryId, visibleState.data.draft_updated_at, action, reason.trim())
      const status: ReplyDraftStatus | null = updated.draft?.status ?? (action === 'approve' ? 'ready_to_send' : 'rejected')
      remove(inquiryId)
      setAction(null)
      setDecided(true)
      setState((current) => current.kind !== 'ready' ? current : {
        key: loadKey,
        kind: 'ready',
        data: { ...current.data, draft_status: status, review_state: 'not_awaiting', allowed_actions: [] },
      })
      void refresh(true)
      try {
        const latest = await fetchSupervisorReview(inquiryId)
        setState({ key: loadKey, kind: 'ready', data: latest })
      } catch (error) {
        if (error instanceof UnauthorizedError) onUnauthorized()
        else setRefreshError(describeError(error))
      }
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        onUnauthorized()
      } else if (error instanceof ApiError && error.status === 409) {
        setActionError(describeError(error, 'write'))
        try {
          const previous = visibleState.data.draft_updated_at
          const latest = await load(loadKey)
          if (latest.draft_updated_at !== previous) setRequiresReview(true)
          if (!latest.allowed_actions.includes(action)) setAction(null)
          void refresh(true)
        } catch (refreshError) {
          if (refreshError instanceof UnauthorizedError) onUnauthorized()
          else setRefreshError(describeError(refreshError))
        }
      } else {
        setActionError(describeError(error, 'write'))
      }
    } finally {
      setSaving(false)
    }
  }

  function openInspector() {
    void navigate({ to: '/approvals/$inquiryId/run', params: { inquiryId: String(inquiryId) } })
  }

  if (visibleState.kind === 'loading') return <p role="status">{t('supervisor.review.loading')}</p>
  if (visibleState.kind === 'error') {
    return (
      <Card role="alert" className="gap-0 rounded-lg py-4 shadow-none">
        <CardContent className="grid justify-items-start gap-3">
          <p className="text-destructive">{errorMessage(visibleState.error, t)}</p>
          <Button type="button" variant="outline" onClick={() => setAttempt((value) => value + 1)}>{t('common.retry')}</Button>
          <Link className="text-primary underline underline-offset-4" to="/approvals">{t('supervisor.review.back')}</Link>
        </CardContent>
      </Card>
    )
  }

  const review = visibleState.data
  const awaiting = review.draft_status === 'awaiting_supervisor' && review.review_state !== 'not_awaiting'
  const canApprove = review.allowed_actions.includes('approve')
  const canReject = review.allowed_actions.includes('reject')
  const attention = review.policy?.rules.filter((rule) => rule.verdict !== 'pass') ?? []
  const customer = review.context.fields?.customer

  return (
    <div className="grid min-w-0 gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link className="text-primary underline underline-offset-4" to="/approvals">{t('supervisor.review.back')}</Link>
        <Button ref={inspectorTrigger} type="button" variant="outline" onClick={openInspector}>{t('inspector.open')}</Button>
      </div>
      {refreshError && <p role="alert" className="text-destructive">{errorMessage(refreshError, t)}</p>}
      {actionError && <p role="alert" className="text-destructive">{errorMessage(actionError, t)}</p>}
      <Card className="gap-0 rounded-lg shadow-none">
        <CardContent className="grid min-w-0 gap-3 p-4">
          <header className="grid gap-1">
            <h2 ref={resultHeading} tabIndex={-1} className="text-xl font-semibold focus-visible:outline-2 focus-visible:outline-ring">
              {review.subject}
            </h2>
            <p className="text-sm text-muted-foreground">
              {customer ? `${customer} · ` : ''}{review.sender_name} &lt;{review.sender_email}&gt; · {formatDate(review.received_at)}
            </p>
            {review.submitted_at && <p className="text-sm text-muted-foreground">{t('supervisor.review.submitted', { date: formatDate(review.submitted_at) })}</p>}
          </header>

          {/* Always mounted, so the result set after a decision is announced. */}
          <p role="status" className={awaiting ? 'sr-only' : 'rounded-md border bg-muted p-3'}>
            {awaiting ? '' : t('supervisor.review.result', { status: review.draft_status ? t(`draft.status.${review.draft_status}`) : t('supervisor.state.not_awaiting') })}
          </p>
          {awaiting && review.review_state !== 'actionable' && (
            <p className="rounded-md border border-warning bg-warning/10 p-3">{t(`supervisor.state.${review.review_state}`)}</p>
          )}

          <section aria-labelledby="supervisor-attention-heading" className="grid gap-2">
            <h3 id="supervisor-attention-heading" className="font-semibold">{t('supervisor.review.attention')}</h3>
            {attention.length === 0 ? <p className="text-sm text-muted-foreground">{t('supervisor.review.noAttention')}</p> : (
              <ul className="grid gap-2 sm:grid-cols-3">
                {attention.map((rule) => <li key={rule.code} className="grid content-start gap-1 rounded-md border p-2 text-sm">
                  <span className="font-medium">{t(RULE_LABEL[rule.code])}</span>{' '}
                  <span className="text-destructive">{t(VERDICT_LABEL[rule.verdict].key)}</span>{' '}
                  <span>{policyReason(rule, t)}</span>
                </li>)}
              </ul>
            )}
          </section>

          <section aria-labelledby="supervisor-offer-heading" className="grid gap-2">
            <h3 id="supervisor-offer-heading" className="font-semibold">{t('supervisor.review.offer')}</h3>
            {review.offer_unavailable || review.offer === null ? <p role="alert" className="text-destructive">{t('supervisor.review.offerUnavailable')}</p> : (
              <div className="grid gap-2 rounded-md border p-2 sm:grid-cols-2">
                <p className="text-sm">{t('supervisor.review.coverage')}: {t('common.coverage', { covered: review.offer.covered_quantity, requested: review.offer.requested_quantity })}</p>
                <p className="text-sm">{t('supervisor.review.fulfilled')}: {review.offer.fulfilled_on}</p>
                <p className="text-sm">{t('supervisor.review.value')}: {formatPln(review.offer.value)}</p>
                <p className="text-sm">{t('supervisor.review.margin')}: {formatPercent(review.offer.margin_percent)}</p>
                {review.offer.edited && <p className="font-medium">{t('supervisor.review.edited')}</p>}
                <ul className="grid gap-2 sm:col-span-2 sm:grid-cols-3">
                  {review.offer.lines.map((line, index) => <li key={`${line.product_code}-${index}`} className="grid content-start gap-1 rounded-md bg-muted p-2">
                    <p className="text-sm font-medium">{line.product_name} ({line.product_code})</p>
                    <p className="text-xs leading-4">{line.quantity} × {formatPln(line.unit_price)} · {sourceText(line, t)}</p>
                  </li>)}
                </ul>
              </div>
            )}
          </section>

          {awaiting && (canApprove || canReject) && (
            <section aria-labelledby="supervisor-decision-heading" className="grid gap-3 rounded-lg border bg-card p-4">
              <h3 id="supervisor-decision-heading" className="font-semibold">{t('supervisor.review.decision')}</h3>
              <div className="flex flex-wrap gap-2">
                {canApprove && <Button type="button" variant={action === 'approve' ? 'default' : 'outline'} onClick={() => setAction('approve')}>{t('common.approve')}</Button>}
                {canReject && <Button type="button" variant={action === 'reject' ? 'default' : 'outline'} onClick={() => setAction('reject')}>{t('common.reject')}</Button>}
              </div>
              {action !== null && <form onSubmit={(event) => { event.preventDefault(); void submitDecision() }} className="grid gap-3">
                <Label htmlFor="supervisor-reason">{t('draft.form.reasonRequired')}</Label>
                <textarea id="supervisor-reason" required rows={3} className="min-h-20 resize-y rounded-md border border-input bg-background px-3 py-2" value={reason} onChange={(event) => setReason(event.target.value)} />
                {requiresReview && <p className="text-sm text-destructive">{t('supervisor.review.readAgain')}</p>}
                <Button type="submit" disabled={saving || !reason.trim() || requiresReview}>
                  {saving ? t('common.saving') : t(action === 'approve' ? 'supervisor.review.confirmApprove' : 'supervisor.review.confirmReject')}
                </Button>
                {requiresReview && <Button type="button" variant="outline" onClick={() => setRequiresReview(false)}>{t('supervisor.review.reviewed')}</Button>}
              </form>}
            </section>
          )}
          {awaiting && !canApprove && !canReject && <p role="alert" className="text-destructive">{t('supervisor.review.noActions')}</p>}

          <details className="rounded-md border p-3">
            <summary className="cursor-pointer font-medium">{t('supervisor.review.context')}</summary>
            <div className="grid gap-4 pt-3">
              {review.policy && <ul className="grid gap-2">
                {review.policy.rules.map((rule) => <li key={rule.code} className="flex flex-wrap gap-x-2">
                  <span className="font-medium">{t(RULE_LABEL[rule.code])}</span>
                  <span>{t(VERDICT_LABEL[rule.verdict].key)}</span>
                  <span>{policyReason(rule, t)}</span>
                </li>)}
              </ul>}
              {review.offer_body && <details><summary className="cursor-pointer">{t('supervisor.review.email')}</summary><div className="grid gap-2 pt-2"><p className="font-medium">{review.offer_subject}</p><p className="whitespace-pre-wrap">{review.offer_body}</p></div></details>}
              <details><summary className="cursor-pointer">{t('supervisor.review.originalEmail')}</summary><p className="whitespace-pre-wrap pt-2">{review.body}</p></details>
              {review.decisions.length > 0 && <DecisionHistory inquiryId={inquiryId} decisions={review.decisions} />}
            </div>
          </details>
        </CardContent>
      </Card>
      <RunInspector analysis={analysis} loading={analysisLoading} loadError={inspectorError} onRetry={() => { setInspectorError(null); setInspectorResult(null); setInspectorAttempt((value) => value + 1) }} open={inspectorOpen} onClose={() => { setInspectorError(null); void navigate({ to: '/approvals/$inquiryId', params: { inquiryId: String(inquiryId) } }) }} returnFocusTo={inspectorTrigger} />
    </div>
  )
}

export default SupervisorReview
