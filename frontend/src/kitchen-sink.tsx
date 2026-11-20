// Dev-only kitchen sink (frontend/kitchen-sink.html, served by `npm run dev`): the real shell
// components in the 7-state matrix, fed by a stubbed `fetch` with static data. Not built.
// The captions are developer notes and stay in English; the components follow the PL | EN switch.
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { createMemoryHistory, RouterContextProvider, RouterProvider } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import './index.css'
import './i18n'
import type { Analysis, ChecksView, OrchestrationView, RunSummary } from './api/analysis'
import type { SupervisorQueue as SupervisorQueueData, SupervisorReview as SupervisorReviewData } from './api/supervisor'
import type { User } from './api/auth'
import type { InquiryDetail, InquirySummary } from './api/inquiries'
import AppNav from './components/AppNav'
import AnalysisPanel from './components/AnalysisPanel'
import AppShell from './components/AppShell'
import Inbox from './components/Inbox'
import LanguageSwitch from './components/LanguageSwitch'
import LoginForm from './components/LoginForm'
import SystemPage from './components/SystemPage'
import SupervisorQueue from './components/SupervisorQueue'
import SupervisorReview from './components/SupervisorReview'
import PolicySection from './components/PolicySection'
import VariantComparison from './components/VariantComparison'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { createAppRouter } from './router'
import { SessionContext, type Session } from './session'
import { SupervisorQueueProvider } from './supervisorQueue'
import {
  ACME_ORCHESTRATION,
  COMPATIBILITY_TASK,
  DELTA_ORCHESTRATION,
  HISTORY_TASK,
  orchestrationRun,
  SUPPLIER_TASK,
} from './test/orchestrationFixtures'
import { ACME_POLICY, DELTA_POLICY } from './test/policyFixtures'
import {
  ACME_LATE_RECOMMENDATION,
  ACME_MANY_VARIANTS_RECOMMENDATION,
  ACME_RECOMMENDATION,
  DELTA_RECOMMENDATION,
} from './test/recommendationFixtures'
import {
  ACME_APPROVED,
  ACME_DRAFT,
  DELTA_AWAITING,
  DELTA_DRAFT,
  DELTA_SUBMITTED,
  DELTA_SUPERVISOR_REJECTED,
} from './test/replyDraftFixtures'
import { SALES, SUPERVISOR as REVIEWER } from './test/userFixtures'

// --- Static data --------------------------------------------------------------------

const SUPERVISOR: User = { id: 1, username: 'anna', display_name: 'Anna Nowak', role: 'supervisor' }

function inquiry(id: number, fields: Partial<InquirySummary>): InquirySummary {
  return {
    id,
    sender_name: 'Jan Kowalski',
    sender_email: 'jan@example.com',
    subject: 'Zapytanie ofertowe: 200 szt. łożysk 6204',
    received_at: '2026-11-16T09:30:00Z',
    source: 'sample',
    outcome: null,
    draft_status: null,
    analyzed: false,
    ...fields,
  }
}

// Every badge the list can show: E-mail and the seven statuses (awaiting supervisor, analysed,
// needs input, new, exception, ready to send, rejected).
const INQUIRIES = [
  inquiry(1, {
    source: 'mailbox', analyzed: true, draft_status: 'awaiting_supervisor', outcome: 'exception',
  }),
  inquiry(2, { sender_name: 'Maria Wiśniewska', analyzed: true, outcome: 'standard' }),
  inquiry(3, { source: 'mailbox', sender_name: 'Piotr Zieliński', analyzed: true, outcome: 'needs_input' }),
  inquiry(4, { sender_name: 'Firma Długa-Nazwa Sp. z o.o.', subject: 'Re: termin dostawy' }),
  inquiry(5, { sender_name: 'Ewa Lis', analyzed: true, outcome: 'exception', draft_status: 'draft' }),
  inquiry(6, {
    sender_name: 'Tomasz Mazur', analyzed: true, outcome: 'exception', draft_status: 'ready_to_send',
  }),
  inquiry(7, {
    sender_name: 'Alicja Dąbrowska', analyzed: true, outcome: 'exception', draft_status: 'rejected',
  }),
]
const NONE_AWAITING = INQUIRIES.filter((item) => item.draft_status !== 'awaiting_supervisor')

function detail(summary: InquirySummary): InquiryDetail {
  return { ...summary, body: 'Dzień dobry, prosimy o ofertę na 80 szt. ABC-100 do piątku.' }
}

// --- Run inspector data (the test fixtures of the seed inquiries) ---------------------

const PARSE_RUN: RunSummary = {
  id: 3,
  status: 'completed',
  started_at: '2026-11-10T09:00:00Z',
  duration_ms: 1520.4,
  steps: [
    {
      id: 10, name: 'parse', kind: 'llm', status: 'ok', error_type: null, provider: 'groq',
      model: 'openai/gpt-oss-120b', input_tokens: 1200, output_tokens: 300, cache_read_tokens: 0,
      cache_write_tokens: 0, cost_usd: '0.0003600000', price_status: 'priced',
      price_source: 'genai-prices 0.2.1', started_at: '2026-11-10T09:00:00Z', duration_ms: 1500.2,
    },
    {
      id: 11, name: 'resolve-deadline', kind: 'deterministic', status: 'ok', error_type: null,
      provider: null, model: null, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0,
      cache_write_tokens: 0, cost_usd: null, price_status: 'not_applicable', price_source: null,
      started_at: '2026-11-10T09:00:01Z', duration_ms: 0.4,
    },
  ],
  totals: {
    input_tokens: 1200, output_tokens: 300, cache_read_tokens: 0, cost_usd: '0.0003600000',
    cost_complete: true, steps_duration_ms: 1500.6, duration_ms: 1520.4,
  },
}

function analysisOf(inquiryId: number, overrides: Partial<Analysis> = {}): Analysis {
  const fields = {
    customer: 'ACME Sp. z o.o.', product_code: 'ABC-100', quantity: 80, deadline: '2026-11-06',
    deadline_text: 'do piątku', substitute_allowed: true, price_kind: 'best_price' as const,
    price_value: null, price_text: 'najlepsza cena',
  }
  return {
    inquiry_id: inquiryId, extractor: 'groq', reference_date: '2026-11-02', fields,
    model_fields: fields, uncertain: {}, corrected_fields: [],
    analyzed_at: '2026-11-10T09:00:01Z', analyzed_by_name: 'Anna Nowak', corrected_at: null,
    corrected_by_name: null, run: PARSE_RUN, checks: null, orchestration: ACME_ORCHESTRATION,
    recommendation: ACME_RECOMMENDATION, policy: ACME_POLICY, draft: ACME_DRAFT, decisions: [],
    ...overrides,
  }
}

const SUPERVISOR_QUEUE: SupervisorQueueData = {
  total: 4,
  items: [
    { id: 31, sender_name: 'Hurtownia Delta', subject: 'Edited offer review', received_at: '2026-11-16T09:30:00Z', submitted_at: '2026-11-16T10:00:00Z', submitted_by: 2, draft_updated_at: DELTA_AWAITING.updated_at, attention_rules: [{ code: 'margin', verdict: 'fail' }, { code: 'discount', verdict: 'fail' }], review_state: 'actionable' },
    { id: 32, sender_name: 'ACME', subject: 'Own submission', received_at: '2026-11-16T09:30:00Z', submitted_at: '2026-11-16T10:10:00Z', submitted_by: SUPERVISOR.id, draft_updated_at: DELTA_AWAITING.updated_at, attention_rules: [{ code: 'order_value', verdict: 'not_evaluated' }], review_state: 'actionable' },
    { id: 33, sender_name: 'Biuro Max', subject: 'Out-of-date submission', received_at: '2026-11-16T09:30:00Z', submitted_at: '2026-11-16T10:20:00Z', submitted_by: 2, draft_updated_at: DELTA_AWAITING.updated_at, attention_rules: [], review_state: 'stale' },
    { id: 34, sender_name: 'Omega', subject: 'Offer details unavailable', received_at: '2026-11-16T09:30:00Z', submitted_at: '2026-11-16T10:30:00Z', submitted_by: null, draft_updated_at: DELTA_AWAITING.updated_at, attention_rules: [], review_state: 'unavailable' },
  ],
}

function supervisorReviewOf(
  inquiryId: number,
  overrides: Partial<SupervisorReviewData> = {},
): SupervisorReviewData {
  return {
    inquiry_id: inquiryId,
    sender_name: 'Hurtownia Delta',
    sender_email: 'zakupy@delta.example.com',
    subject: 'Zamówienie ABC-100',
    body: MAIL_BODY,
    received_at: '2026-11-16T09:30:00Z',
    draft_status: 'awaiting_supervisor',
    draft_updated_at: DELTA_AWAITING.updated_at,
    submitted_at: '2026-11-16T10:00:00Z',
    submitted_by: 2,
    review_state: 'actionable',
    allowed_actions: ['approve', 'reject'],
    offer: DELTA_AWAITING.offer,
    offer_unavailable: false,
    offer_subject: DELTA_AWAITING.subject,
    offer_body: DELTA_AWAITING.body,
    policy: DELTA_AWAITING.policy,
    context: {
      fields: analysisOf(inquiryId).fields,
      checks: EXCEPTION_CHECKS,
      orchestration: null,
      recommendation: null,
      policy: DELTA_AWAITING.policy,
    },
    decisions: [DELTA_SUBMITTED],
    ...overrides,
  }
}

// A partial orchestration: the supplier agent failed twice, the rest of the plan ran.
const FAILED_ORCHESTRATION: OrchestrationView = {
  ...ACME_ORCHESTRATION,
  status: 'partial',
  tasks: [
    COMPATIBILITY_TASK,
    {
      ...SUPPLIER_TASK,
      status: 'failed',
      steps: ['agent:supplier-availability', 'agent:supplier-availability'],
      error_type: 'TimeoutError',
      result: null,
    },
    HISTORY_TASK,
  ],
  run: orchestrationRun([
    ['agent:substitute-compatibility', 1.5],
    ['agent:supplier-availability', 2],
    ['agent:customer-history', 3],
  ]),
}

// --- Step view data (AnalysisPanel, one inquiry id per state) -------------------------------
// The panel is rendered by itself with the e-mail body and a user; it loads its analysis from
// the stubbed fetch (DEFAULTS), so each cell's data is fixed by its inquiry id.

const MAIL_BODY =
  'Dzień dobry,\n\nprosimy o ofertę na 80 szt. ABC-100 (lub zamiennik) z dostawą do piątku.\n\nZ poważaniem\nJan Kowalski'

const EXCEPTION_CHECKS: ChecksView = {
  outcome: 'exception',
  exception_type: 'insufficient_stock',
  reasons: [],
  results: {
    customer: { status: 'matched', matched_by: 'name', customer_id: 1, name: 'ACME', candidates: [] },
    stock: {
      status: 'insufficient', product_code: 'ABC-100', product_name: 'Czujnik ciśnienia ABC-100',
      requested: 80, available: 50, shortage: 30,
    },
    price: {
      status: 'ok', list_price: '120.00', discount_percent: '5.00', unit_price: '114.00',
      total: '9120.00', currency: 'PLN',
    },
    discount: { status: 'ok', standard_percent: '5.00', requested_kind: 'best_price', requested_value: null },
    credit: { status: 'ok', limit: '30000.00', balance: '2000.00', order_value: '9120.00' },
    reasons: [],
  },
  checked_at: '2026-11-10T09:00:02Z',
  stale: false,
  uncertain_inputs: [],
  run: null,
}
const STANDARD_CHECKS: ChecksView = {
  ...EXCEPTION_CHECKS,
  outcome: 'standard',
  exception_type: null,
  results: {
    ...EXCEPTION_CHECKS.results,
    stock: { ...EXCEPTION_CHECKS.results.stock, status: 'ok', requested: 20, shortage: 0 },
  },
}
const NEEDS_INPUT_CHECKS: ChecksView = {
  ...EXCEPTION_CHECKS,
  outcome: 'needs_input',
  exception_type: null,
  reasons: ['customer_missing'],
}

// ACME exception with every stage current (analysisOf's defaults): the draft is awaiting a decision.
const AT_APPROVAL: Partial<Analysis> = { checks: EXCEPTION_CHECKS }
// Hurtownia Delta: the policy stage requires a supervisor.
const DELTA_BASE: Partial<Analysis> = {
  checks: EXCEPTION_CHECKS,
  orchestration: DELTA_ORCHESTRATION,
  recommendation: DELTA_RECOMMENDATION,
  policy: DELTA_POLICY,
}

type PanelCase = {
  id: number
  anchor: string
  label: string
  user: User
  // null: not analysed; 'pending': never answers (loading)
  analysis: Partial<Analysis> | null | 'pending'
  path?: string
}

const PANEL_CASES = {
  loading: { id: 10, anchor: 'step-loading', label: 'Step view: analysis loading', user: SALES, analysis: 'pending' },
  notAnalysed: {
    id: 11, anchor: 'step-not-analysed', label: 'Step view: not analysed (Inquiry, Analyze request)',
    user: SALES, analysis: null,
  },
  needsInput: {
    id: 12, anchor: 'step-needs-input', label: 'Step view: needs_input (Inquiry, missing customer)', user: SALES,
    analysis: { checks: NEEDS_INPUT_CHECKS, orchestration: null, recommendation: null, policy: null, draft: null },
  },
  standard: {
    id: 13, anchor: 'step-standard', label: 'Step view: standard (Inquiry done, later steps not needed)', user: SALES,
    analysis: { checks: STANDARD_CHECKS, orchestration: null, recommendation: null, policy: null, draft: null },
  },
  variantsFailed: {
    id: 14, anchor: 'step-variants-failed', label: 'Step view: exception at Variants, failed recommendation', user: SALES,
    analysis: {
      ...AT_APPROVAL,
      recommendation: {
        ...ACME_RECOMMENDATION, status: 'failed', choice: null,
        error: { kind: 'recommender_failed', code: 'rate_limited', message: 'Rate limit reached' },
      },
      policy: null,
      draft: null,
    },
  },
  manyVariants: {
    id: 20, anchor: 'step-variants-many', label: 'Step view: Variants, five variants (two substitutes, a combined one; scroll hint on a narrow screen)',
    user: SALES,
    analysis: { ...AT_APPROVAL, recommendation: ACME_MANY_VARIANTS_RECOMMENDATION, policy: null, draft: null },
  },
  noDeadline: {
    id: 21, anchor: 'step-variants-no-deadline', label: 'Step view: Variants, the inquiry has no customer deadline', user: SALES,
    analysis: {
      ...DELTA_BASE,
      fields: {
        customer: 'Hurtownia Delta', product_code: 'ABC-100', quantity: 500, deadline: null,
        deadline_text: null, substitute_allowed: null, price_kind: 'best_price' as const,
        price_value: null, price_text: null,
      },
      policy: null,
      draft: null,
    },
  },
  lateRecommended: {
    id: 22, anchor: 'step-variants-late', label: 'Step view: Variants, the recommended variant misses the deadline', user: SALES,
    analysis: { ...AT_APPROVAL, recommendation: ACME_LATE_RECOMMENDATION, policy: null, draft: null },
  },
  approval: {
    id: 15, anchor: 'step-approval-draft', label: 'Step view: Approval, current draft (salesperson)',
    user: SALES, analysis: AT_APPROVAL,
  },
  approvalSupervisor: {
    id: 23, anchor: 'step-approval-requires-supervisor',
    label: 'Step view: Approval, verdict requires a supervisor (Send to supervisor, with the hint)',
    user: SALES, analysis: { ...DELTA_BASE, draft: DELTA_DRAFT, decisions: [] },
  },
  awaitingSales: {
    id: 16, anchor: 'step-awaiting-sales', label: 'Step view: awaiting supervisor, as the salesperson who submitted it',
    user: SALES, analysis: { ...DELTA_BASE, draft: DELTA_AWAITING, decisions: [DELTA_SUBMITTED] },
  },
  awaitingSupervisor: {
    id: 17, anchor: 'step-awaiting-supervisor', label: 'Step view: awaiting supervisor, as a supervisor (decides)',
    user: REVIEWER, analysis: { ...DELTA_BASE, draft: DELTA_AWAITING, decisions: [DELTA_SUBMITTED] },
  },
  rejected: {
    id: 18, anchor: 'step-rejected', label: 'Step view: rejected by the supervisor (Approval, with the reason)', user: SALES,
    analysis: {
      ...DELTA_BASE,
      draft: { ...DELTA_DRAFT, status: 'rejected' },
      decisions: [DELTA_SUBMITTED, DELTA_SUPERVISOR_REJECTED],
    },
  },
  ready: {
    id: 19, anchor: 'step-ready-to-send', label: 'Step view: ready_to_send (Reply)', user: SALES,
    analysis: { ...AT_APPROVAL, draft: { ...ACME_DRAFT, status: 'ready_to_send' }, decisions: [ACME_APPROVED] },
  },
  unavailableStepLink: {
    id: 23, anchor: 'step-unavailable-link', label: 'Step URL: unavailable Reply link falls back to Inquiry', user: SALES,
    analysis: { checks: STANDARD_CHECKS, orchestration: null, recommendation: null, policy: null, draft: null },
    path: '/inquiries/23?step=reply',
  },
} satisfies Record<string, PanelCase>

function PanelCell({ panel }: { panel: PanelCase }) {
  return (
    <Cell id={panel.anchor} label={`${panel.label} · #${panel.anchor}`} wide>
      <Routed path={panel.path}>
        <AnalysisPanel inquiryId={panel.id} body={MAIL_BODY} user={panel.user} onUnauthorized={() => {}} />
      </Routed>
    </Cell>
  )
}

// Compatibility examples use their own historical data, never current analysis fields.
const LEGACY_POLICY = {
  ...DELTA_POLICY,
  rules: DELTA_POLICY.rules.map((rule) => ({ ...rule, reason_code: undefined })),
}
const LEGACY_RECOMMENDATION = {
  ...ACME_RECOMMENDATION,
  options: ACME_RECOMMENDATION.options.map((option) => ({
    ...option,
    signals: option.signals.map(({ code, polarity, label }) => ({ code, polarity, label })),
  })),
}
const UNKNOWN_POLICY = {
  ...ACME_POLICY,
  rules: [{ ...ACME_POLICY.rules[0], reason_code: 'future_margin', reason: 'Historyczna uwaga biznesowa' }],
}
const UNKNOWN_RECOMMENDATION = {
  ...ACME_RECOMMENDATION,
  options: ACME_RECOMMENDATION.options.map((option) => ({
    ...option,
    signals: [...option.signals, { code: 'future_business_signal', polarity: 'info' as const, label: 'Oryginalna uwaga o ofercie' }],
  })),
}

// --- fetch stub -----------------------------------------------------------------------
// Every request gets a reply from `scope` when one is set, else from DEFAULTS. A scope is set
// only while a scenario's own code runs synchronously: around its components' mount effects
// (<Stub>) and around a driven click or submit (`withReplies`). The API modules call `fetch`
// synchronously from both, so no reply can reach another cell.

type Reply = { status: number; body?: unknown } | 'pending' | 'network-error'
type Replies = Record<string, Reply>

const SUPERVISOR_REVIEWS: Record<number, SupervisorReviewData> = {
  31: supervisorReviewOf(31, {
    offer: { ...DELTA_AWAITING.offer, edited: true },
    policy: {
      ...DELTA_AWAITING.policy!,
      rules: DELTA_AWAITING.policy!.rules.map((rule) =>
        rule.code === 'margin' ? { ...rule, verdict: 'fail' } : rule,
      ),
    },
  }),
  32: supervisorReviewOf(32, { submitted_by: SUPERVISOR.id, allowed_actions: ['reject'] }),
  33: supervisorReviewOf(33, { review_state: 'stale', allowed_actions: ['reject'] }),
  34: supervisorReviewOf(34, { review_state: 'unavailable', allowed_actions: ['reject'], offer: null, offer_unavailable: true }),
  35: supervisorReviewOf(35, {
    draft_status: 'ready_to_send',
    review_state: 'not_awaiting',
    allowed_actions: [],
    submitted_by: null,
    decisions: [DELTA_SUBMITTED, ACME_APPROVED],
  }),
  36: supervisorReviewOf(36, {
    draft_status: 'rejected',
    review_state: 'not_awaiting',
    allowed_actions: [],
    submitted_by: null,
    decisions: [DELTA_SUBMITTED, DELTA_SUPERVISOR_REJECTED],
  }),
}

const DEFAULTS: Replies = {
  'GET /api/auth/me': { status: 200, body: SUPERVISOR },
  'GET /api/inquiries': { status: 200, body: INQUIRIES },
  'GET /api/health': { status: 200, body: { status: 'ok', database: 'ok', migration: '0012' } },
  'POST /api/auth/login': { status: 200, body: SUPERVISOR },
  'POST /api/auth/logout': { status: 204 },
  'POST /api/mailbox/fetch': { status: 200, body: { fetched: 3, created: 2, duplicates: 1, skipped: 0 } },
  'GET /api/supervisor/queue': { status: 200, body: SUPERVISOR_QUEUE },
  ...Object.fromEntries(
    Object.entries(SUPERVISOR_REVIEWS).map(([id, review]): [string, Reply] => [
      `GET /api/supervisor/reviews/${id}`,
      { status: 200, body: review },
    ]),
  ),
  // The inquiry view behind the run inspector cells, one inquiry per state. Fetched after the
  // session resolves, so they cannot come from a cell's scope.
  ...Object.fromEntries(
    INQUIRIES.map((item): [string, Reply] => [`GET /api/inquiries/${item.id}`, { status: 200, body: detail(item) }]),
  ),
  'GET /api/inquiries/60/analysis': { status: 200, body: null },
  'GET /api/inquiries/61/analysis': { status: 200, body: null },
  'GET /api/inquiries/1/analysis': { status: 200, body: analysisOf(1) },
  'GET /api/inquiries/2/analysis': 'pending',
  'GET /api/inquiries/3/analysis': { status: 200, body: null },
  'GET /api/inquiries/4/analysis': {
    status: 200,
    body: analysisOf(4, { orchestration: FAILED_ORCHESTRATION, recommendation: null, policy: null, draft: null }),
  },
  // The step view cells (PANEL_CASES), one inquiry id per state.
  ...Object.fromEntries(
    Object.values<PanelCase>(PANEL_CASES).map((panel): [string, Reply] => [
      `GET /api/inquiries/${panel.id}/analysis`,
      panel.analysis === 'pending'
        ? 'pending'
        : { status: 200, body: panel.analysis === null ? null : analysisOf(panel.id, panel.analysis) },
    ]),
  ),
}
let scope: Replies | null = null

window.fetch = (input, init) => {
  const path = typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url
  const key = `${init?.method ?? 'GET'} ${path}`
  const reply = scope?.[key] ??
    DEFAULTS[key] ?? { status: 404, body: { detail: `Not stubbed in the kitchen sink: ${key}` } }
  if (reply === 'network-error') return Promise.reject(new TypeError('Simulated lost response'))
  if (reply === 'pending') {
    return new Promise((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })
  }
  const body = reply.body === undefined ? null : JSON.stringify(reply.body)
  return Promise.resolve(
    new Response(body, { status: reply.status, headers: { 'Content-Type': 'application/json' } }),
  )
}

function withReplies(replies: Replies, action: () => void) {
  scope = replies
  try {
    action()
  } finally {
    scope = null
  }
}

// React runs mount effects in tree order, so the children's effects (their first fetches)
// run between ScopeOpen's and ScopeClose's. Later fetches (Retry, after sign-in) get DEFAULTS.
function ScopeOpen({ replies }: { replies: Replies }) {
  useEffect(() => {
    scope = replies
  }, [replies])
  return null
}

function ScopeClose() {
  useEffect(() => {
    scope = null
  }, [])
  return null
}

function Stub({ replies, children }: { replies: Replies; children: ReactNode }) {
  const [initialReplies] = useState(() => replies)
  return (
    <>
      <ScopeOpen replies={initialReplies} />
      {children}
      <ScopeClose />
    </>
  )
}

// --- Routing ----------------------------------------------------------------------------
// Each cell gets its own router on memory history, so clicks inside a cell never touch the
// page's address.

function memoryRouter(path: string) {
  return createAppRouter(createMemoryHistory({ initialEntries: [path] }))
}

// The whole app (App as the root layout) at `path`. The route is matched before the first
// render, so App's session fetch runs inside the Stub's scope, as it did for `<App />`.
function RoutedApp({ replies, path = '/' }: { replies: Replies; path?: string }) {
  const [router] = useState(() => memoryRouter(path))
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let live = true
    router.load().then(
      () => live && setReady(true),
      (error: unknown) => console.error(error),
    )
    return () => {
      live = false
    }
  }, [router])
  if (!ready) return null
  return (
    <Stub replies={replies}>
      <RouterProvider router={router} />
    </Stub>
  )
}

const SESSION: Session = { user: SUPERVISOR, onUnauthorized: () => {} }

// The whole app at inquiry `inquiryId`. The run inspector is a modal Sheet over the page, so
// the cell opens it only on request: the button (or the "How was this calculated?" link)
// moves the cell's own router to /inquiries/$id/run; Esc or Close returns.
function InspectorCell({ inquiryId }: { inquiryId: number }) {
  const [router] = useState(() => memoryRouter(`/inquiries/${inquiryId}`))
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let live = true
    router.load().then(
      () => live && setReady(true),
      (error: unknown) => console.error(error),
    )
    return () => {
      live = false
    }
  }, [router])
  if (!ready) return null
  const open = () =>
    void router.navigate({ to: '/inquiries/$inquiryId/run', params: { inquiryId: String(inquiryId) } })
  return (
    <>
      <div className="border-b bg-card px-3 py-2">
        <Button type="button" size="sm" variant="outline" onClick={open}>
          Open run inspector
        </Button>
      </div>
      <Stub replies={SIGNED_IN}>
        <RouterProvider router={router} />
      </Stub>
    </>
  )
}

// A view outside App (Inbox, AppNav): the signed-in session and a router for its links. With a
// `path`, the route is matched before the view mounts, so the view reads that address (its
// `?step=`, for the analysis panel).
function Routed({ children, path }: { children: ReactNode; path?: string }) {
  const [router] = useState(() => memoryRouter(path ?? '/'))
  const [ready, setReady] = useState(path === undefined)
  useEffect(() => {
    if (path === undefined) return
    let live = true
    router.load().then(
      () => live && setReady(true),
      (error: unknown) => console.error(error),
    )
    return () => {
      live = false
    }
  }, [router, path])
  if (!ready) return null
  return (
    <RouterContextProvider router={router}>
      <SessionContext.Provider value={SESSION}>
        <SupervisorQueueProvider user={SUPERVISOR} onUnauthorized={() => {}}>
          {children}
        </SupervisorQueueProvider>
      </SessionContext.Provider>
    </RouterContextProvider>
  )
}

// --- Driving a component into a state (typing, clicking) --------------------------------

async function find<T extends Element>(root: HTMLElement, selector: string): Promise<T> {
  for (let attempt = 0; attempt < 100; attempt++) {
    const element = root.querySelector<T>(selector)
    if (element) return element
    await new Promise((resolve) => setTimeout(resolve, 20))
  }
  throw new Error(`kitchen sink: "${selector}" not found`)
}

// Sets the value the way a user does, so React's onChange fires.
function type(input: HTMLInputElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

async function signIn(root: HTMLElement, reply: Reply) {
  type(await find(root, 'input[name="username"]'), 'anna')
  type(await find(root, 'input[name="password"]'), 'secret')
  const form = await find<HTMLFormElement>(root, 'form')
  withReplies({ 'POST /api/auth/login': reply }, () => form.requestSubmit())
}

async function clickFetchMail(root: HTMLElement, reply: Reply) {
  const button = await find<HTMLButtonElement>(root, '[role="region"] button')
  withReplies({ 'POST /api/mailbox/fetch': reply }, () => button.click())
}

function Driven({ drive, children }: { drive: (root: HTMLElement) => Promise<void>; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  // Once per mount; changing language keeps existing errors and does not repeat requests.
  const [first] = useState(() => drive)
  useEffect(() => {
    if (ref.current) first(ref.current).catch((error: unknown) => console.error(error))
  }, [first])
  return <div ref={ref}>{children}</div>
}

// Replies per scenario (module constants, so a Stub's scope is a stable object).
const SESSION_ERROR: Replies = { 'GET /api/auth/me': { status: 500, body: { detail: 'Database unavailable' } } }
const SESSION_PENDING: Replies = { 'GET /api/auth/me': 'pending' }
const SIGNED_IN: Replies = { 'GET /api/auth/me': { status: 200, body: SUPERVISOR } }
const LIST_ERROR: Replies = { 'GET /api/inquiries': { status: 500, body: { detail: 'Database unavailable' } } }
const LIST_PENDING: Replies = { 'GET /api/inquiries': 'pending' }
const NO_INQUIRIES: Replies = { 'GET /api/inquiries': { status: 200, body: [] } }
const NONE_AWAITING_LIST: Replies = { 'GET /api/inquiries': { status: 200, body: NONE_AWAITING } }
const HEALTH_DEGRADED: Replies = {
  'GET /api/health': { status: 503, body: { status: 'degraded', database: 'error', migration: null } },
}
const HEALTH_ERROR: Replies = { 'GET /api/health': { status: 502 } }
const HEALTH_PENDING: Replies = { 'GET /api/health': 'pending' }

// --- Layout -----------------------------------------------------------------------------

function Section({ state, caption, children }: { state: string; caption: string; children: ReactNode }) {
  return (
    <section className="grid gap-3" aria-labelledby={`state-${state}`}>
      <h2 id={`state-${state}`} className="text-xl font-bold">
        {state}
      </h2>
      <p className="text-sm text-muted-foreground">{caption}</p>
      <div className="grid gap-4 lg:grid-cols-2">{children}</div>
    </section>
  )
}

// `shell` cells hold an AppShell, whose min-h-screen is cancelled so the cell fits its content.
function Cell({ id, label, wide, shell, children }: { id?: string; label: string; wide?: boolean; shell?: boolean; children: ReactNode }) {
  return (
    <div id={id} className={cn('min-w-0 overflow-clip rounded-lg border', wide && 'lg:col-span-2')}>
      <p className="border-b bg-card px-3 py-1.5 text-sm text-muted-foreground">{label}</p>
      <div className={cn(shell ? '*:min-h-0' : 'bg-background p-4')}>{children}</div>
    </div>
  )
}

function NotApplicable({ items }: { items: [string, string][] }) {
  return (
    <Cell label="N/A" wide>
      <ul className="grid gap-1 text-sm">
        {items.map(([what, why]) => (
          <li key={what}>
            <span className="font-semibold">{what}: N/A</span> <span className="text-muted-foreground">— {why}</span>
          </li>
        ))}
      </ul>
    </Cell>
  )
}

const BADGE_VARIANTS = [
  'default', 'secondary', 'destructive', 'outline', 'success', 'warning',
  'success-outline', 'warning-outline', 'destructive-outline',
] as const
const BUTTON_VARIANTS = ['default', 'outline', 'secondary', 'ghost', 'destructive', 'link'] as const

// The look each control has on hover / keyboard focus, applied as static classes so every one
// shows at once. Buttons and inputs: shadcn ring (outline-none + 3px solid ring-ring). Plain
// elements (the inbox rows): the base :focus-visible outline from index.css.
const HOVER = {
  default: 'bg-primary/90',
  outline: 'bg-accent text-accent-foreground dark:bg-input/50',
  secondary: 'bg-secondary/80',
  ghost: 'bg-accent text-accent-foreground dark:bg-accent/50',
  destructive: 'bg-destructive/90',
  link: 'underline',
} as const satisfies Record<(typeof BUTTON_VARIANTS)[number], string>
const RING_LOOK = 'border-ring ring-3 ring-ring'
const OUTLINE_LOOK = 'outline-2 outline-offset-2 outline-ring'
const ROW = 'grid w-full gap-0.5 rounded-md border bg-card px-4 py-2 text-left'

function Row({ className }: { className?: string }) {
  return (
    <button type="button" className={cn(ROW, className)}>
      <span className="font-semibold">{INQUIRIES[1].sender_name}</span>
      <span>{INQUIRIES[1].subject}</span>
    </button>
  )
}

// --- Page -------------------------------------------------------------------------------

function KitchenSink() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-card px-4 py-2">
        <p className="font-semibold">Kitchen sink · 7-state matrix</p>
        <LanguageSwitch />
      </div>
      {/* Existing descriptors translate on render without remounting or repeating requests. */}
      <main className="mx-auto grid max-w-7xl gap-10 px-4 py-6">
        <Section state="default" caption="Signed out (login) and signed in (inbox list with every badge it shows: the seven statuses and E-mail), plus the ui primitives.">
          <Cell label="Header logged out + login" shell>
            <AppShell user={null}>
              <LoginForm onSignedIn={() => {}} />
            </AppShell>
          </Cell>
          <Cell label="Badge and Button variants (ui primitives)">
            <div className="grid gap-3">
              <div className="flex flex-wrap gap-2">
                {BADGE_VARIANTS.map((variant) => (
                  <Badge key={variant} variant={variant}>{variant}</Badge>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {BUTTON_VARIANTS.map((variant) => (
                  <Button key={variant} type="button" variant={variant}>{variant}</Button>
                ))}
              </div>
            </div>
          </Cell>
          <Cell label="Header logged in with nav + inbox list (selecting a row opens the inquiry view, not stubbed here)" wide shell>
            <Routed>
              <AppShell user={SUPERVISOR} onSignOut={() => {}} nav={<AppNav />}>
                <Inbox />
              </AppShell>
            </Routed>
          </Cell>
          <Cell label="System page (/system): ok, with Refresh">
            <SystemPage />
          </Cell>
          <Cell label="Supervisor queue: one shared list and count, with several awaiting states" wide>
            <Routed><SupervisorQueue /></Routed>
          </Cell>
          <Cell label="Supervisor review: edited offer and decision" wide>
            <Routed><SupervisorReview inquiryId={31} /></Routed>
          </Cell>
          <Cell label="Supervisor review: own submission (reject only)" wide>
            <Routed><SupervisorReview inquiryId={32} /></Routed>
          </Cell>
          <Cell label="Supervisor review: stale submission (reject only)" wide>
            <Routed><SupervisorReview inquiryId={33} /></Routed>
          </Cell>
          <Cell label="Supervisor review: unavailable offer (reject only)" wide>
            <Routed><SupervisorReview inquiryId={34} /></Routed>
          </Cell>
          <Cell label="Supervisor review: approved result" wide>
            <Routed><SupervisorReview inquiryId={35} /></Routed>
          </Cell>
          <Cell label="Supervisor review: rejected result" wide>
            <Routed><SupervisorReview inquiryId={36} /></Routed>
          </Cell>
          <Cell label="Run inspector: every run, the plan by stage and the grand total (inquiry 1; the header shows its status)" wide shell>
            <InspectorCell inquiryId={1} />
          </Cell>
          <PanelCell panel={PANEL_CASES.needsInput} />
          <PanelCell panel={PANEL_CASES.standard} />
          <Cell id="business-legacy" label="Business messages: historical records without metadata (generic translated descriptions)" wide>
            <PolicySection inquiryId={50} policy={LEGACY_POLICY} recommendation={LEGACY_RECOMMENDATION} disabled={false} running={false} onRerun={async () => {}} onUnauthorized={() => {}} />
            <VariantComparison recommendation={LEGACY_RECOMMENDATION} expectedDeadline="2026-11-06" />
          </Cell>
          <Cell id="business-unknown" label="Business messages: unknown codes preserve original business text" wide>
            <PolicySection inquiryId={51} policy={UNKNOWN_POLICY} recommendation={UNKNOWN_RECOMMENDATION} disabled={false} running={false} onRerun={async () => {}} onUnauthorized={() => {}} />
            <VariantComparison recommendation={UNKNOWN_RECOMMENDATION} expectedDeadline="2026-11-06" />
          </Cell>
          <PanelCell panel={PANEL_CASES.manyVariants} />
          <PanelCell panel={PANEL_CASES.noDeadline} />
          <PanelCell panel={PANEL_CASES.lateRecommended} />
          <PanelCell panel={PANEL_CASES.approval} />
          <PanelCell panel={PANEL_CASES.approvalSupervisor} />
          <PanelCell panel={PANEL_CASES.awaitingSales} />
          <PanelCell panel={PANEL_CASES.awaitingSupervisor} />
          <PanelCell panel={PANEL_CASES.ready} />
          <PanelCell panel={PANEL_CASES.unavailableStepLink} />
        </Section>

        <Section state="hover" caption="Forced hover look (static classes matching each hover: rule). Hover the real controls in “default” to compare.">
          <Cell label="Buttons, forced hover">
            <div className="flex flex-wrap gap-2">
              {BUTTON_VARIANTS.map((variant) => (
                <Button key={variant} type="button" variant={variant} className={HOVER[variant]} data-state="hover">
                  {variant}
                </Button>
              ))}
            </div>
          </Cell>
          <Cell label="Inbox row: at rest / forced hover (bg-muted) / selected (aria-current)">
            <div className="grid gap-2">
              <Row />
              <Row className="bg-muted" />
              <Row className="border-primary bg-muted" />
            </div>
          </Cell>
          <NotApplicable
            items={[
              ['Input', 'no hover style; only border and focus'],
              ['Badge', 'static label, not interactive'],
            ]}
          />
        </Section>

        <Section state="focus-visible" caption="Forced keyboard-focus look (static classes). Tab through “default” to see the real ring.">
          <Cell label="Buttons and the language switch, forced focus">
            <div className="flex flex-wrap gap-2">
              {BUTTON_VARIANTS.map((variant) => (
                <Button key={variant} type="button" variant={variant} className={RING_LOOK}>{variant}</Button>
              ))}
              <Button type="button" size="sm" variant="ghost" className={RING_LOOK}>EN</Button>
            </div>
          </Cell>
          <Cell label="Input and inbox row, forced focus">
            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="ks-focus-input">{t('login.username')}</Label>
                <Input id="ks-focus-input" defaultValue="anna" className={RING_LOOK} />
              </div>
              <Row className={OUTLINE_LOOK} />
            </div>
          </Cell>
          <NotApplicable items={[['Badge', 'not focusable']]} />
        </Section>

        <Section state="disabled" caption="Each control in its in-progress state, reached by the real flow against a request that never answers.">
          <Cell label="Sign in: submitting" shell>
            <Driven drive={(root) => signIn(root, 'pending')}>
              <AppShell user={null}>
                <LoginForm onSignedIn={() => {}} />
              </AppShell>
            </Driven>
          </Cell>
          <Cell label="Sign out: signing out (AppShell signingOut, owned by App)" shell>
            <AppShell user={SUPERVISOR} signingOut>
              <p className="text-muted-foreground">…</p>
            </AppShell>
          </Cell>
          <Cell label="Fetch mail: fetching" wide>
            <Driven drive={(root) => clickFetchMail(root, 'pending')}>
              <Routed>
                <Inbox />
              </Routed>
            </Driven>
          </Cell>
          <NotApplicable
            items={[
              ['Login fields', 'LoginForm disables only the button while submitting'],
              ['Retry, awaiting filter, language switch', 'never disabled'],
            ]}
          />
        </Section>

        <Section state="error" caption="Error text next to the field or action that failed. Switch PL/EN while an error is visible: existing state is preserved without repeating requests.">
          <Cell id="error-permission" label="Permission denied (403); Retry reloads successfully" wide>
            <Stub replies={{ 'GET /api/inquiries': { status: 403, body: { code: 'SUPERVISOR_REQUIRED', detail: 'Supervisor role required' } } }}>
              <Routed><Inbox /></Routed>
            </Stub>
          </Cell>
          <Cell id="error-validation" label="Login validation (422); entered fields stay available" shell>
            <Driven drive={(root) => signIn(root, { status: 422, body: { code: 'VALIDATION_ERROR', detail: [{ msg: 'Private validator diagnostic' }] } })}>
              <AppShell user={null}><LoginForm onSignedIn={() => {}} /></AppShell>
            </Driven>
          </Cell>
          <Cell id="error-unknown" label="Unknown code and private detail: safe translated fallback" wide>
            <Stub replies={{ 'GET /api/inquiries': { status: 500, body: { code: 'FUTURE_CODE', detail: 'SQL private exception diagnostic' } } }}>
              <Routed><Inbox /></Routed>
            </Stub>
          </Cell>
          <Cell id="error-conflict" label="Concurrent change (409); read current state first" wide>
            <Driven drive={async (root) => {
              const button = await find<HTMLButtonElement>(root, '[role="tabpanel"] button')
              withReplies({ 'POST /api/inquiries/60/analysis': { status: 409, body: { code: 'DRAFT_CHANGED', detail: 'Draft changed, reload' } } }, () => button.click())
            }}>
              <Routed><AnalysisPanel inquiryId={60} body={MAIL_BODY} user={SALES} onUnauthorized={() => {}} /></Routed>
            </Driven>
          </Cell>
          <Cell id="error-write-uncertain" label="Lost response after write; never assume it was not saved" wide>
            <Driven drive={async (root) => {
              const button = await find<HTMLButtonElement>(root, '[role="tabpanel"] button')
              withReplies({ 'POST /api/inquiries/61/analysis': 'network-error' }, () => button.click())
            }}>
              <Routed><AnalysisPanel inquiryId={61} body={MAIL_BODY} user={SALES} onUnauthorized={() => {}} /></Routed>
            </Driven>
          </Cell>
          <Cell label="Supervisor queue refresh failed; the last count stays visible" wide>
            <Driven drive={async (root) => {
              const refresh = await find<HTMLButtonElement>(root, 'button')
              withReplies({ 'GET /api/supervisor/queue': { status: 500, body: { detail: 'Unavailable' } } }, () => refresh.click())
            }}>
              <Routed><SupervisorQueue /></Routed>
            </Driven>
          </Cell>
          <Cell label="Login: invalid credentials (401)" shell>
            <Driven drive={(root) => signIn(root, { status: 401, body: { detail: 'Invalid username or password', code: 'INVALID_CREDENTIALS' } })}>
              <AppShell user={null}>
                <LoginForm onSignedIn={() => {}} />
              </AppShell>
            </Driven>
          </Cell>
          <Cell label="Session check failed (App, 500) with Retry" shell>
            <RoutedApp replies={SESSION_ERROR} />
          </Cell>
          <Cell label="Inbox list failed (500) with Retry; Fetch mail failed (502)" wide>
            <Stub replies={LIST_ERROR}>
              <Driven drive={(root) => clickFetchMail(root, { status: 502, body: { detail: 'Mailbox unavailable' } })}>
                <Routed>
                  <Inbox />
                </Routed>
              </Driven>
            </Stub>
          </Cell>
          <Cell label="Sign out failed (App, logout 500)" wide shell>
            <Driven
              drive={async (root) => {
                // The language buttons carry aria-pressed; Sign out does not.
                const signOut = await find<HTMLButtonElement>(root, 'header button:not([aria-pressed])')
                withReplies({ 'POST /api/auth/logout': { status: 500 } }, () => signOut.click())
              }}
            >
              <RoutedApp replies={SIGNED_IN} />
            </Driven>
          </Cell>
          <Cell label="System page: degraded (health 503, database error)">
            <Stub replies={HEALTH_DEGRADED}>
              <SystemPage />
            </Stub>
          </Cell>
          <Cell label="System page: unavailable (health 502)">
            <Stub replies={HEALTH_ERROR}>
              <SystemPage />
            </Stub>
          </Cell>
          <Cell label="Run inspector: a failed agent task with its error type (inquiry 4)" wide shell>
            <InspectorCell inquiryId={4} />
          </Cell>
          <PanelCell panel={PANEL_CASES.variantsFailed} />
          <PanelCell panel={PANEL_CASES.rejected} />
          <NotApplicable items={[['Language switch', 'bundled resources, nothing to fail']]} />
        </Section>

        <Section state="empty" caption="Lists with nothing to show.">
          <Cell label="Supervisor queue: empty">
            <Stub replies={{ 'GET /api/supervisor/queue': { status: 200, body: { items: [], total: 0 } } }}>
              <Routed><SupervisorQueue /></Routed>
            </Stub>
          </Cell>
          <Cell label="No inquiries" wide>
            <Stub replies={NO_INQUIRIES}>
              <Routed>
                <Inbox />
              </Routed>
            </Stub>
          </Cell>
          <Cell label="None awaiting a supervisor (filter on)" wide>
            <Stub replies={NONE_AWAITING_LIST}>
              <Driven drive={async (root) => (await find<HTMLButtonElement>(root, '[role="region"] button[aria-pressed]')).click()}>
                <Routed>
                  <Inbox />
                </Routed>
              </Driven>
            </Stub>
          </Cell>
          <Cell label="Run inspector: the inquiry has no analysis (inquiry 3)" wide shell>
            <InspectorCell inquiryId={3} />
          </Cell>
          <PanelCell panel={PANEL_CASES.notAnalysed} />
          <NotApplicable items={[['Login, header', 'always have content']]} />
        </Section>

        <Section state="loading" caption="Requests that never answer.">
          <Cell label="Supervisor queue loading">
            <Stub replies={{ 'GET /api/supervisor/queue': 'pending' }}>
              <Routed><SupervisorQueue /></Routed>
            </Stub>
          </Cell>
          <Cell label="Session check (App)" shell>
            <RoutedApp replies={SESSION_PENDING} />
          </Cell>
          <Cell label="Inbox list loading" wide>
            <Stub replies={LIST_PENDING}>
              <Routed>
                <Inbox />
              </Routed>
            </Stub>
          </Cell>
          <Cell label="System page: checking">
            <Stub replies={HEALTH_PENDING}>
              <SystemPage />
            </Stub>
          </Cell>
          <Cell label="Run inspector: the analysis is loading (inquiry 2)" wide shell>
            <InspectorCell inquiryId={2} />
          </Cell>
          <PanelCell panel={PANEL_CASES.loading} />
          <NotApplicable
            items={[
              ['Sign in, Sign out, Fetch mail', 'their in-progress state is the disabled label, shown under “disabled”'],
              ['Language switch', 'synchronous, bundled resources'],
            ]}
          />
        </Section>
      </main>
    </div>
  )
}

// No StrictMode: its double mount would drive every cell twice.
createRoot(document.getElementById('root')!).render(<KitchenSink />)
