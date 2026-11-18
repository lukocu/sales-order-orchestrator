import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { renderWithRouter } from '../test/renderWithRouter'
import { SALES } from '../test/userFixtures'

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

it('translates an existing login failure without resubmitting or clearing credentials', async () => {
  let accepted = false
  let loginWrites = 0
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/api/auth/me') return json(401, { code: 'NOT_AUTHENTICATED', detail: 'Not authenticated' })
    if (path === '/api/auth/login') {
      loginWrites += 1
      return accepted ? json(200, SALES) : json(401, { code: 'INVALID_CREDENTIALS', detail: 'SQLSTATE private_password technical failure' })
    }
    if (path === '/api/inquiries') return json(200, [])
    throw new Error('Unexpected request')
  })
  vi.stubGlobal('fetch', fetchMock)
  await renderWithRouter('/')
  const username = await screen.findByLabelText('Username')
  const password = screen.getByLabelText('Password')
  fireEvent.change(username, { target: { value: 'sales' } })
  fireEvent.change(password, { target: { value: 'mistyped' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toMatch(/username|password|sign.in/i)
  expect(alert).not.toHaveTextContent(/SQLSTATE|private_password|technical/)
  const english = alert.textContent
  const calls = fetchMock.mock.calls.length
  await act(async () => { await i18n.changeLanguage('pl') })
  expect(alert.textContent).not.toBe(english)
  expect(alert.textContent).toMatch(/hasł|logowania|dane|nazw/i)
  expect(username).toHaveValue('sales')
  expect(password).toHaveValue('mistyped')
  expect(fetchMock).toHaveBeenCalledTimes(calls)
  expect(loginWrites).toBe(1)
  accepted = true
  fireEvent.change(password, { target: { value: 'corrected' } })
  fireEvent.click(screen.getByRole('button', { name: 'Zaloguj się' }))
  expect(await screen.findByText(SALES.display_name)).toBeInTheDocument()
  expect(loginWrites).toBe(2)
})

it('updates a read failure on language switch and recovers only after explicit retry', async () => {
  let failed = true
  let listReads = 0
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === '/api/auth/me') return json(200, SALES)
    if (String(input) === '/api/inquiries') {
      listReads += 1
      return failed ? json(503, { code: 'DATABASE_UNAVAILABLE', detail: 'SQL connection pool secret host' }) : json(200, [])
    }
    throw new Error('Unexpected request')
  })
  vi.stubGlobal('fetch', fetchMock)
  await renderWithRouter('/')
  const alert = await screen.findByRole('alert')
  expect(alert).not.toHaveTextContent(/SQL|pool|secret|host|HTTP/)
  const english = alert.textContent
  await act(async () => { await i18n.changeLanguage('pl') })
  expect(alert.textContent).not.toBe(english)
  expect(listReads).toBe(1)
  failed = false
  fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  expect(listReads).toBe(2)
})

it('localizes malformed health responses without revealing diagnostic client messages', async () => {
  let healthReads = 0
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === '/api/auth/me') return json(200, SALES)
    healthReads += 1
    return new Response('<private upstream failure>', { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  await renderWithRouter('/system')
  await screen.findByText('System status')
  const status = await screen.findByRole('status')
  await waitFor(() => expect(status).not.toHaveTextContent(/Checking/))
  expect(status).not.toHaveTextContent(/Invalid response body|private upstream|JSON|HTTP/)
  const english = status.textContent
  await act(async () => { await i18n.changeLanguage('pl') })
  expect(status.textContent).not.toBe(english)
  expect(healthReads).toBe(1)
})