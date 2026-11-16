import { createContext, useContext } from 'react'
import type { User } from './api/auth'

export type Session = {
  user: User
  // Called whenever the API answers 401 (session gone): App shows sign-in in place.
  onUnauthorized: () => void
}

// Provided by App while signed in; the routed views read the user and the 401 handler here.
export const SessionContext = createContext<Session | null>(null)

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (session === null) throw new Error('useSession must be used inside a signed-in App')
  return session
}
