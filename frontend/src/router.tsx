import {
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from '@tanstack/react-router'
import App from './App'
import InboxRoute from './components/InboxRoute'
import NotFound from './components/NotFound'

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
})

// Opens the run inspector in Phase 3; no component of its own yet.
const inquiryRunRoute = createRoute({
  getParentRoute: () => inquiryRoute,
  path: '/run',
})

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/system',
  // The system page arrives in Phase 2.
  component: () => null,
})

const routeTree = rootRoute.addChildren([
  inboxRoute.addChildren([indexRoute, inquiryRoute.addChildren([inquiryRunRoute])]),
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
