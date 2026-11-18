import { createContext } from 'react'
import type { SupervisorQueue } from './api/supervisor'

export type QueueState =
  | { kind: 'loading' }
  | { kind: 'ready'; queue: SupervisorQueue; stale: false }
  | { kind: 'error'; error: unknown; previous: SupervisorQueue | null }

export type QueueContextValue = {
  state: QueueState
  refresh: (force?: boolean) => Promise<void>
  remove: (inquiryId: number) => void
}

export const SupervisorQueueContext = createContext<QueueContextValue | null>(null)
