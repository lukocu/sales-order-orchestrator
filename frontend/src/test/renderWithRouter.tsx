import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { createAppRouter } from '../router'

// Renders the whole app (App as the root layout) through the real route tree at `path`.
// The route is matched before the first render, so the root layout (App) mounts in it, as
// `render(<App />)` did. The returned router exposes `router.state.location`.
export async function renderWithRouter(path: string) {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }))
  await router.load()
  render(<RouterProvider router={router} />)
  return router
}
