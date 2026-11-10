import { useState, type FormEvent } from 'react'
import { login, UnauthorizedError, type User } from '../api/auth'

type Props = {
  onSignedIn: (user: User) => void
}

function LoginForm({ onSignedIn }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const user = await login(username, password)
      onSignedIn(user)
    } catch (err) {
      setError(
        err instanceof UnauthorizedError
          ? 'Invalid username or password'
          : err instanceof Error
            ? err.message
            : 'Sign in failed',
      )
      setSubmitting(false)
    }
  }

  return (
    <section className="card login">
      <h2>Sign in</h2>
      <form className="login__form" onSubmit={handleSubmit}>
        <label>
          Username
          <input
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  )
}

export default LoginForm
