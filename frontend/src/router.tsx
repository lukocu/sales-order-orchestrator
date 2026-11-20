import {
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from '@tanstack/react-router'
import App from './App'
import InboxRoute from './components/InboxRoute'
import NotFound from './components/NotFound'
import SystemPage from './components/SystemPage'
import { SupervisorQueueRoute, SupervisorReviewRoute } from './components/SupervisorRoutes'

// Code-based tree: no route generator. No path starts with /api (the server keeps those).
const rootRoute = createRootRoute({
  component: App,
  notFoundComponent: NotFound,
})

// Pathless layout shared by the inbox addresses.
const inboxRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'inbox',
  component: InboxRoute,
})

const indexRoute = createRoute({
  getParentRoute: () => inboxRoute,
  path: '/',
})

const inquiryRoute = createRoute({
  getParentRoute: () => inboxRoute,
  path: '/inquiries/$inquiryId',
  validateSearch: (search: Record<string, unknown>): { step?: string } => ({
    step: typeof search.step === 'string' ? search.step : undefined,
  }),
})

// Opens the run inspector in Phase 3; no component of its own yet.
const inquiryRunRoute = createRoute({
  getParentRoute: () => inquiryRoute,
  path: '/run',
})

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/system',
  component: SystemPage,
})

const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/approvals',
  component: SupervisorQueueRoute,
})

const approvalReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/approvals/$inquiryId',
  component: () => <SupervisorReviewRoute />,
})

const approvalRunRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/approvals/$inquiryId/run',
  component: () => <SupervisorReviewRoute inspectorOpen />,
})

const routeTree = rootRoute.addChildren([
  inboxRoute.addChildren([indexRoute, inquiryRoute.addChildren([inquiryRunRoute])]),
  approvalsRoute,
  approvalReviewRoute,
  approvalRunRoute,
  systemRoute,
])

// The app passes nothing (browser history); tests and the kitchen sink pass memory history.
export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
