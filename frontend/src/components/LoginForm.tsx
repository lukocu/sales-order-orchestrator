import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { login, UnauthorizedError, type User } from '../api/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Props = {
  onSignedIn: (user: User) => void
}

function LoginForm({ onSignedIn }: Props) {
  const { t } = useTranslation()
  const id = useId()
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
          ? t('login.invalidCredentials')
          : err instanceof Error
            ? err.message
            : t('login.failed'),
      )
      setSubmitting(false)
    }
  }

  return (
    <Card className="gap-4 rounded-lg py-5 shadow-none">
      <CardHeader>
        <CardTitle className="text-lg">
          <h2>{t('login.title')}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor={`${id}-username`}>{t('login.username')}</Label>
            <Input
              id={`${id}-username`}
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`${id}-password`}>{t('login.password')}</Label>
            <Input
              id={`${id}-password`}
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <Button type="submit" className="justify-self-start" disabled={submitting}>
            {submitting ? t('login.submitting') : t('login.submit')}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export default LoginForm
