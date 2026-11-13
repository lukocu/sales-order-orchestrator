import type { User } from '../api/auth'

// The demo accounts as GET /api/auth/me returns them, plus a second supervisor for the
// four-eyes rule.

export const SALES: User = {
  id: 1,
  username: 'sales',
  display_name: 'Anna Kowalska',
  role: 'salesperson',
}

export const SUPERVISOR: User = {
  id: 2,
  username: 'supervisor',
  display_name: 'Piotr Nowak',
  role: 'supervisor',
}

export const OTHER_SUPERVISOR: User = {
  id: 3,
  username: 'supervisor2',
  display_name: 'Ewa Wiśniewska',
  role: 'supervisor',
}
