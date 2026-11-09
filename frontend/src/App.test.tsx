import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Health } from './api/health'

function stubFetch(status: number, body: Health) {
  const fetchMock = vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('App', () => {
  it('shows the ok state with the migration revision', async () => {
    const fetchMock = stubFetch(200, {
      status: 'ok',
      database: 'ok',
      migration: '0001_baseline',
    })

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Sales Order Orchestrator' })).toBeInTheDocument()
    expect(screen.getByText('Checking…')).toBeInTheDocument()
    expect(await screen.findByText('All systems operational')).toBeInTheDocument()
    expect(screen.getByText('0001_baseline')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('shows the degraded state when the API answers 503', async () => {
    stubFetch(503, { status: 'degraded', database: 'error', migration: null })

    render(<App />)

    expect(await screen.findByText('Degraded')).toBeInTheDocument()
    expect(screen.getByText('error')).toBeInTheDocument()
    expect(screen.getByText('unknown')).toBeInTheDocument()
  })

  it('shows an error when the API cannot be reached', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    render(<App />)

    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText('API unreachable')).toBeInTheDocument()
  })
})
