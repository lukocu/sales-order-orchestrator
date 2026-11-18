import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { UnauthorizedError } from '../api/auth'
import {
  fetchInquiries,
  fetchInquiry,
  type InquiryDetail,
  type InquirySummary,
} from '../api/inquiries'
import { fetchMail, type FetchResult } from '../api/mailbox'
import { describeError, type ErrorDescriptor } from '../api/errorMessages'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useSession } from '../session'
import AnalysisPanel from './AnalysisPanel'
import { errorMessage, formatDate } from './format'
import { inquiryStatus, STATUS_VARIANT, type InquiryStatusFacts } from './inquiryStatus'

type Props = {
  // The open inquiry, parsed from /inquiries/$inquiryId by the route; null on `/`.
  selectedId?: number | null
}

// Keep descriptors in state; visible messages follow the current UI language.
type ListState =
  | { kind: 'loading' }
  | { kind: 'ok'; inquiries: InquirySummary[] }
  | { kind: 'error'; error: ErrorDescriptor }

type DetailState =
  | { id: number; kind: 'ok'; inquiry: InquiryDetail }
  | { id: number; kind: 'error'; error: ErrorDescriptor }

type FetchStatus = { kind: 'ok'; result: FetchResult } | { kind: 'error'; error: ErrorDescriptor }

function sameFacts(a: InquiryStatusFacts, b: InquiryStatusFacts): boolean {
  return a.analyzed === b.analyzed && a.outcome === b.outcome && a.draft_status === b.draft_status
}

// The one status of an inquiry; the text is always there, the colour only supports it.
function StatusBadge({ facts }: { facts: InquiryStatusFacts }) {
  const { t } = useTranslation()
  const status = inquiryStatus(facts)
  return (
    <Badge variant={STATUS_VARIANT[status]}>
      <span className="sr-only">{t('inquiryStatus.label')}: </span>
      {t(`inquiryStatus.${status}`)}
    </Badge>
  )
}

// "2 new, 3 already in inbox, 1 skipped"; `fetched` is the sum and adds nothing.
function fetchSummary({ created, duplicates, skipped }: FetchResult, t: TFunction): string {
  const parts: string[] = []
  if (created === 0) parts.push(t('inbox.fetchNoNew'))
  else {
    parts.push(t('inbox.fetchNew', { count: created }))
    if (duplicates > 0) parts.push(t('inbox.fetchDuplicates', { count: duplicates }))
  }
  if (skipped > 0) parts.push(t('inbox.fetchSkipped', { count: skipped }))
  return parts.join(', ')
}

function Inbox({ selectedId = null }: Props) {
  const { t } = useTranslation()
  // `onUnauthorized` is called whenever the API answers 401 (session gone).
  const { user, onUnauthorized } = useSession()
  const [list, setList] = useState<ListState>({ kind: 'loading' })
  const [listAttempt, setListAttempt] = useState(0)
  const [detail, setDetail] = useState<DetailState | null>(null)
  const [awaitingOnly, setAwaitingOnly] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [fetchStatus, setFetchStatus] = useState<FetchStatus | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchInquiries(controller.signal).then(
      (inquiries) => setList({ kind: 'ok', inquiries }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onUnauthorized()
        else {
          const descriptor = describeError(error)
          if (descriptor !== null) setList({ kind: 'error', error: descriptor })
        }
      },
    )
    return () => controller.abort()
  }, [listAttempt, onUnauthorized])

  useEffect(() => {
    if (selectedId === null) return
    const controller = new AbortController()
    fetchInquiry(selectedId, controller.signal).then(
      (inquiry) => setDetail({ id: selectedId, kind: 'ok', inquiry }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onUnauthorized()
        else {
          const descriptor = describeError(error)
          if (descriptor !== null) setDetail({ id: selectedId, kind: 'error', error: descriptor })
        }
      },
    )
    return () => controller.abort()
  }, [selectedId, onUnauthorized])

  // The panel reports the status facts after loading the analysis and after every change of
  // it (an analysis, a correction, a re-run, a decision, a regenerated or dropped draft); the
  // list item and the open inquiry are updated in place, without fetching again.
  const handleStatusFacts = useCallback((inquiryId: number, facts: InquiryStatusFacts) => {
    setList((current) =>
      current.kind !== 'ok'
        ? current
        : {
            ...current,
            inquiries: current.inquiries.map((inquiry) =>
              inquiry.id === inquiryId && !sameFacts(inquiry, facts)
                ? {
                    ...inquiry,
                    ...facts,
                    draft_status:
                      inquiry.draft_status === 'awaiting_supervisor' && facts.draft_status === null
                        ? inquiry.draft_status
                        : facts.draft_status,
                  }
                : inquiry,
            ),
          },
    )
    setDetail((current) =>
      current?.kind === 'ok' && current.id === inquiryId && !sameFacts(current.inquiry, facts)
        ? {
            ...current,
            inquiry: {
              ...current.inquiry,
              ...facts,
              draft_status:
                current.inquiry.draft_status === 'awaiting_supervisor' && facts.draft_status === null
                  ? current.inquiry.draft_status
                  : facts.draft_status,
            },
          }
        : current,
    )
  }, [])

  function retryList() {
    setList({ kind: 'loading' })
    setListAttempt((n) => n + 1)
  }

  // The list is fetched again without the loading state, so it stays on screen (and the
  // selection with it) until the new one arrives.
  async function handleFetchMail() {
    setFetching(true)
    setFetchStatus(null)
    try {
      const result = await fetchMail()
      setFetchStatus({ kind: 'ok', result })
      setListAttempt((n) => n + 1)
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        onUnauthorized()
        return
      }
      const descriptor = describeError(error, 'write')
      if (descriptor !== null) setFetchStatus({ kind: 'error', error: descriptor })
    } finally {
      setFetching(false)
    }
  }

  // The detail fetched for an earlier selection is stale until the new one arrives.
  const currentDetail = detail !== null && detail.id === selectedId ? detail : null

  // The header shows what the list shows; the detail's own facts when the list has no such item.
  const headerFacts =
    currentDetail?.kind === 'ok'
      ? (list.kind === 'ok'
          ? list.inquiries.find((inquiry) => inquiry.id === currentDetail.id)
          : undefined) ?? currentDetail.inquiry
      : null

  const awaiting =
    list.kind === 'ok'
      ? list.inquiries.filter((inquiry) => inquiry.draft_status === 'awaiting_supervisor')
      : []
  const shown = list.kind !== 'ok' ? [] : awaitingOnly ? awaiting : list.inquiries

  return (
    <div className="grid items-start gap-4 md:grid-cols-5">
      <Card
        role="region"
        aria-labelledby="inbox-heading"
        className="min-w-0 gap-0 rounded-lg py-5 shadow-none md:col-span-2"
      >
        <CardContent className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <h2 id="inbox-heading" className="text-lg font-semibold">
              {t('inbox.heading')}
            </h2>
            <Button type="button" onClick={handleFetchMail} disabled={fetching}>
              {fetching ? t('inbox.fetching') : t('inbox.fetchMail')}
            </Button>
          </div>
          <div className="empty:hidden" aria-live="polite">
            {fetchStatus !== null && (
              <p
                className={
                  fetchStatus.kind === 'error' ? 'text-destructive' : 'text-muted-foreground'
                }
              >
                {fetchStatus.kind === 'ok'
                  ? fetchSummary(fetchStatus.result, t)
                  : errorMessage(fetchStatus.error, t)}
              </p>
            )}
          </div>
          {list.kind === 'loading' && (
            <p className="text-muted-foreground">{t('inbox.loading')}</p>
          )}
          {list.kind === 'error' && (
            <div role="alert" className="grid justify-items-start gap-2">
              <p className="text-destructive">{errorMessage(list.error, t)}</p>
              <Button type="button" variant="outline" onClick={retryList}>
                {t('inbox.retry')}
              </Button>
            </div>
          )}
          {list.kind === 'ok' && list.inquiries.length > 0 && (
            <Button
              type="button"
              variant={awaitingOnly ? 'default' : 'outline'}
              size="sm"
              className="justify-self-start"
              aria-pressed={awaitingOnly}
              onClick={() => setAwaitingOnly((on) => !on)}
            >
              {t('inbox.awaitingOnly', { count: awaiting.length })}
            </Button>
          )}
          {list.kind === 'ok' && list.inquiries.length === 0 && (
            <p className="text-muted-foreground">{t('inbox.empty')}</p>
          )}
          {list.kind === 'ok' && list.inquiries.length > 0 && shown.length === 0 && (
            <p className="text-muted-foreground">{t('inbox.emptyAwaiting')}</p>
          )}
          {shown.length > 0 && (
            <ul className="grid gap-2">
              {shown.map((inquiry) => {
                const selected = inquiry.id === selectedId
                return (
                  <li key={inquiry.id}>
                    {/* Links to the inquiry's address; the router marks the open one
                        aria-current="page". */}
                    <Link
                      to="/inquiries/$inquiryId"
                      params={{ inquiryId: String(inquiry.id) }}
                      activeProps={{}}
                      className={cn(
                        'grid w-full gap-0.5 rounded-md border bg-card px-4 py-2 text-left transition-colors hover:bg-muted',
                        selected && 'border-primary bg-muted',
                      )}
                    >
                      <span className="font-semibold wrap-anywhere">{inquiry.sender_name}</span>
                      <span className="wrap-anywhere" data-field="subject">
                        {inquiry.subject}
                      </span>
                      <span className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                        <time
                          className="text-sm text-muted-foreground"
                          dateTime={inquiry.received_at}
                        >
                          {formatDate(inquiry.received_at)}
                        </time>
                        <span className="flex flex-wrap gap-1">
                          {inquiry.source === 'mailbox' && (
                            <Badge variant="outline" className="text-muted-foreground">
                              {t('inbox.badgeMailbox')}
                            </Badge>
                          )}
                          <StatusBadge facts={inquiry} />
                        </span>
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <section className="card md:col-span-3" aria-label={t('inbox.detailLabel')}>
        {selectedId === null && <p className="muted">{t('inbox.selectPrompt')}</p>}
        {selectedId !== null && currentDetail === null && (
          <p className="muted">{t('inbox.loadingDetail')}</p>
        )}
        {currentDetail?.kind === 'error' && (
          <p className="error" role="alert">
            {errorMessage(currentDetail.error, t)}
          </p>
        )}
        {currentDetail?.kind === 'ok' && (
          <article>
            <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
              <h3 className="detail__subject font-bold">{currentDetail.inquiry.subject}</h3>
              {headerFacts !== null && <StatusBadge facts={headerFacts} />}
            </div>
            <p className="detail__meta">
              {currentDetail.inquiry.sender_name} &lt;{currentDetail.inquiry.sender_email}&gt;
              {' · '}
              <time dateTime={currentDetail.inquiry.received_at}>
                {formatDate(currentDetail.inquiry.received_at)}
              </time>
            </p>
          </article>
        )}
        {currentDetail?.kind === 'ok' && (
          <AnalysisPanel
            key={currentDetail.inquiry.id}
            inquiryId={currentDetail.inquiry.id}
            body={currentDetail.inquiry.body}
            awaitingSupervisor={currentDetail.inquiry.draft_status === 'awaiting_supervisor'}
            user={user}
            onUnauthorized={onUnauthorized}
            onStatusFacts={handleStatusFacts}
          />
        )}
      </section>
    </div>
  )
}

export default Inbox
