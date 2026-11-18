import { useContext } from 'react'
import { SupervisorQueueContext } from './supervisorQueueContext'

export function useSupervisorQueue() {
  const value = useContext(SupervisorQueueContext)
  if (value === null) throw new Error('useSupervisorQueue must be used inside SupervisorQueueProvider')
  return value
}
