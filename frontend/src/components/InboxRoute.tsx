import { useParams } from '@tanstack/react-router'
import Inbox from './Inbox'
import NotFound from './NotFound'

// A positive integer, or null for anything else ("abc", "0", "1.5", "-2").
function parseInquiryId(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) && id > 0 ? id : null
}

// The component of the pathless layout over `/` and `/inquiries/$inquiryId`: one Inbox for
// both, so it stays mounted (list, filter and fetch status kept) while the selection
// changes. An invalid id shows not-found and fires no request.
function InboxRoute() {
  const { inquiryId } = useParams({ strict: false })
  if (inquiryId === undefined) return <Inbox selectedId={null} />
  const id = parseInquiryId(inquiryId)
  return id === null ? <NotFound /> : <Inbox selectedId={id} />
}

export default InboxRoute
