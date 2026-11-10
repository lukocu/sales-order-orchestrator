import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LoginForm from './LoginForm'

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'sales' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginForm', () => {
  it('shows a message for a wrong password', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: 'Invalid username or password' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    const onSignedIn = vi.fn()

    render(<LoginForm onSignedIn={onSignedIn} />)
    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
    expect(onSignedIn).not.toHaveBeenCalled()
  })

  it('disables the button while signing in', async () => {
    let answer: (response: Response) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => (answer = resolve))),
    )
    const onSignedIn = vi.fn()

    render(<LoginForm onSignedIn={onSignedIn} />)
    fillAndSubmit()

    expect(await screen.findByRole('button', { name: 'Signing in…' })).toBeDisabled()

    const user = { id: 1, username: 'sales', display_name: 'Anna Nowak', role: 'salesperson' }
    answer(new Response(JSON.stringify(user), { status: 200 }))
    await vi.waitFor(() => expect(onSignedIn).toHaveBeenCalledWith(user))
  })

  it('shows the API message for other failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    render(<LoginForm onSignedIn={vi.fn()} />)
    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent('API unreachable')
  })
})
