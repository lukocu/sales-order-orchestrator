import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Health } from '../api/health'
import SystemPage from './SystemPage'

function json(status: number, body: Health): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('SystemPage', () => {
  it('shows the ok state with the migration revision', async () => {
    const fetchMock = vi.fn(async () =>
      json(200, { status: 'ok', database: 'ok', migration: '0001_baseline' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<SystemPage />)

    expect(screen.getByRole('heading', { name: 'System' })).toBeInTheDocument()
    expect(within(screen.getByRole('status')).getByText('Checking…')).toBeInTheDocument()
    expect(
      await within(screen.getByRole('status')).findByText('All systems operational'),
    ).toBeInTheDocument()
    expect(screen.getByText('0001_baseline')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('shows the degraded state when the API answers 503', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(503, { status: 'degraded', database: 'error', migration: null })),
    )

    render(<SystemPage />)

    expect(await within(screen.getByRole('status')).findByText('Degraded')).toBeInTheDocument()
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

    render(<SystemPage />)

    const status = screen.getByRole('status')
    expect(await within(status).findByText('Unavailable')).toBeInTheDocument()
    expect(within(status).getByText('API unreachable')).toBeInTheDocument()
    expect(screen.queryByText('Migration')).not.toBeInTheDocument()
  })

  it('refetches on Refresh', async () => {
    const fetchMock = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(json(503, { status: 'degraded', database: 'error', migration: null }))
      .mockResolvedValueOnce(json(200, { status: 'ok', database: 'ok', migration: '0012' }))
    vi.stubGlobal('fetch', fetchMock)

    render(<SystemPage />)
    expect(await screen.findByText('Degraded')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    expect(await screen.findByText('All systems operational')).toBeInTheDocument()
    expect(screen.getByText('0012')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
