import { useCallback, useEffect, useState } from 'react'
import type { Outcome } from '../api/analysis'
import { logout, ROLE_LABEL, UnauthorizedError, type User } from '../api/auth'
import {
  fetchInquiries,
  fetchInquiry,
  type InquiryDetail,
  type InquirySummary,
} from '../api/inquiries'
import AnalysisPanel from './AnalysisPanel'
import { formatDate } from './format'

type Props = {
  user: User
  // Called after Sign out and whenever the API answers 401 (session gone).
  onSignedOut: () => void
}

type ListState =
  | { kind: 'loading' }
  | { kind: 'ok'; inquiries: InquirySummary[] }
  | { kind: 'error'; message: string }

type DetailState =
  | { id: number; kind: 'ok'; inquiry: InquiryDetail }
  | { id: number; kind: 'error'; message: string }

// Text and colour: the badge never relies on colour alone.
const OUTCOME_LABEL: Record<Outcome, string> = {
  standard: 'Standard',
  exception: 'Exception',
  needs_input: 'Needs input',
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function Inbox({ user, onSignedOut }: Props) {
  const [list, setList] = useState<ListState>({ kind: 'loading' })
  const [listAttempt, setListAttempt] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<DetailState | null>(null)
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchInquiries(controller.signal).then(
      (inquiries) => setList({ kind: 'ok', inquiries }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onSignedOut()
        else setList({ kind: 'error', message: errorMessage(error) })
      },
    )
    return () => controller.abort()
  }, [listAttempt, onSignedOut])

  useEffect(() => {
    if (selectedId === null) return
    const controller = new AbortController()
    fetchInquiry(selectedId, controller.signal).then(
      (inquiry) => setDetail({ id: selectedId, kind: 'ok', inquiry }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof UnauthorizedError) onSignedOut()
        else setDetail({ id: selectedId, kind: 'error', message: errorMessage(error) })
      },
    )
    return () => controller.abort()
  }, [selectedId, onSignedOut])

  // The panel reports the outcome after an analysis, a correction or a re-run of the
  // checks; the list item is updated in place, without fetching the list again.
  const handleOutcome = useCallback((inquiryId: number, outcome: Outcome | null) => {
    setList((current) =>
      current.kind !== 'ok'
        ? current
        : {
            ...current,
            inquiries: current.inquiries.map((inquiry) =>
              inquiry.id === inquiryId && inquiry.outcome !== outcome
                ? { ...inquiry, outcome }
                : inquiry,
            ),
          },
    )
  }, [])

  function retryList() {
    setList({ kind: 'loading' })
    setListAttempt((n) => n + 1)
  }

  async function handleSignOut() {
    setSigningOut(true)
    setSignOutError(null)
    try {
      await logout()
    } catch (error) {
      // A 401 means the session is already gone, which is what Sign out wants.
      if (!(error instanceof UnauthorizedError)) {
        setSignOutError(errorMessage(error))
        setSigningOut(false)
        return
      }
    }
    onSignedOut()
  }

  // The detail fetched for an earlier selection is stale until the new one arrives.
  const currentDetail = detail !== null && detail.id === selectedId ? detail : null

  return (
    <section className="inbox">
      <header className="inbox__header">
        <div>
          <p className="inbox__user">{user.display_name}</p>
          <p className="inbox__role">{ROLE_LABEL[user.role]}</p>
        </div>
        <button type="button" onClick={handleSignOut} disabled={signingOut}>
          Sign out
        </button>
      </header>
      {signOutError && (
        <p className="error" role="alert">
          {signOutError}
        </p>
      )}

      <div className="inbox__body">
        <section className="card inbox__list" aria-labelledby="inbox-heading">
          <h2 id="inbox-heading">Inbox</h2>
          {list.kind === 'loading' && <p className="muted">Loading inquiries…</p>}
          {list.kind === 'error' && (
            <div role="alert">
              <p className="error">{list.message}</p>
              <button type="button" onClick={retryList}>
                Retry
              </button>
            </div>
          )}
          {list.kind === 'ok' && list.inquiries.length === 0 && (
            <p className="muted">No inquiries yet.</p>
          )}
          {list.kind === 'ok' && list.inquiries.length > 0 && (
            <ul className="inquiries">
              {list.inquiries.map((inquiry) => (
                <li key={inquiry.id}>
                  <button
                    type="button"
                    className="inquiry"
                    aria-current={inquiry.id === selectedId ? 'true' : undefined}
                    onClick={() => setSelectedId(inquiry.id)}
                  >
                    <span className="inquiry__sender">{inquiry.sender_name}</span>
                    <span className="inquiry__subject">{inquiry.subject}</span>
                    <span className="inquiry__footer">
                      <time className="inquiry__date" dateTime={inquiry.received_at}>
                        {formatDate(inquiry.received_at)}
                      </time>
                      {inquiry.outcome !== null && (
                        <span className={`badge badge--${inquiry.outcome}`}>
                          {OUTCOME_LABEL[inquiry.outcome]}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card inbox__detail" aria-live="polite" aria-label="Inquiry">
          {selectedId === null && <p className="muted">Select an inquiry to read it.</p>}
          {selectedId !== null && currentDetail === null && (
            <p className="muted">Loading inquiry…</p>
          )}
          {currentDetail?.kind === 'error' && (
            <p className="error" role="alert">
              {currentDetail.message}
            </p>
          )}
          {currentDetail?.kind === 'ok' && (
            <article>
              <h3 className="detail__subject">{currentDetail.inquiry.subject}</h3>
              <p className="detail__meta">
                {currentDetail.inquiry.sender_name} &lt;{currentDetail.inquiry.sender_email}&gt;
                {' · '}
                <time dateTime={currentDetail.inquiry.received_at}>
                  {formatDate(currentDetail.inquiry.received_at)}
                </time>
              </p>
              <div className="detail__body">{currentDetail.inquiry.body}</div>
            </article>
          )}
          {currentDetail?.kind === 'ok' && (
            <AnalysisPanel
              key={currentDetail.inquiry.id}
              inquiryId={currentDetail.inquiry.id}
              onUnauthorized={onSignedOut}
              onOutcome={handleOutcome}
            />
          )}
        </section>
      </div>
    </section>
  )
}

export default Inbox
