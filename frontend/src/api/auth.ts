import { request, requestJson } from './client'

export { ApiError, UnauthorizedError } from './client'

// Mirrors AuthUser in backend/app/auth/deps.py.
export type Role = 'salesperson' | 'supervisor'

export type User = {
  id: number
  username: string
  display_name: string
  role: Role
}

export const ROLE_LABEL: Record<Role, string> = {
  salesperson: 'Salesperson',
  supervisor: 'Supervisor',
}

function isUser(value: unknown): value is User {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.id === 'number' &&
    typeof v.username === 'string' &&
    typeof v.display_name === 'string' &&
    (v.role === 'salesperson' || v.role === 'supervisor')
  )
}

// GET /api/auth/me: the signed-in user, or UnauthorizedError without a valid session.
export function fetchMe(signal?: AbortSignal): Promise<User> {
  return requestJson('/api/auth/me', isUser, { signal })
}

// POST /api/auth/login: sets the session cookie; wrong credentials → UnauthorizedError.
export function login(username: string, password: string): Promise<User> {
  return requestJson('/api/auth/login', isUser, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

// POST /api/auth/logout: ends the session and clears the cookie (204).
export async function logout(): Promise<void> {
  await request('/api/auth/logout', { method: 'POST' })
}
