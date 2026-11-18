import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { UnauthorizedError } from './api/client'
import { fetchSupervisorQueue } from './api/supervisor'
import type { User } from './api/auth'
import type { QueueState } from './supervisorQueueContext'
import { SupervisorQueueContext } from './supervisorQueueContext'

export function SupervisorQueueProvider({
  user,
  onUnauthorized,
  children,
}: {
  user: User
  onUnauthorized: () => void
  children: ReactNode
}) {
  const [state, setState] = useState<QueueState>({ kind: 'loading' })
  const controller = useRef<AbortController | null>(null)
  const request = useRef<Promise<void> | null>(null)
  const generation = useRef(0)
  const previousUser = useRef(user.id)

  const refresh = useCallback(
    async (force = false) => {
      if (user.role !== 'supervisor') return
      if (request.current !== null && !force) return request.current
      if (force) {
        generation.current += 1
        controller.current?.abort()
        request.current = null
      }
      const currentGeneration = ++generation.current
      const abortController = new AbortController()
      controller.current = abortController
      setState((current) =>
        current.kind === 'ready' || (current.kind === 'error' && current.previous !== null)
          ? current
          : { kind: 'loading' },
      )
      const pending = fetchSupervisorQueue(abortController.signal).then(
        (queue) => {
          if (currentGeneration === generation.current) setState({ kind: 'ready', queue, stale: false })
        },
        (error: unknown) => {
          if (abortController.signal.aborted || currentGeneration !== generation.current) return
          if (error instanceof UnauthorizedError) {
            onUnauthorized()
            return
          }
          setState((current) => ({
            kind: 'error',
            error,
            previous: current.kind === 'ready' ? current.queue : current.kind === 'error' ? current.previous : null,
          }))
        },
      ).finally(() => {
        if (currentGeneration === generation.current) {
          request.current = null
          controller.current = null
        }
      })
      request.current = pending
      return pending
    },
    [onUnauthorized, user.role],
  )

  const remove = useCallback((inquiryId: number) => {
    generation.current += 1
    controller.current?.abort()
    request.current = null
    setState((current) => {
      const queue = current.kind === 'ready' ? current.queue : current.kind === 'error' ? current.previous : null
      if (queue === null) return current
      const items = queue.items.filter((item) => item.id !== inquiryId)
      return { kind: 'ready', stale: false, queue: { items, total: items.length } }
    })
  }, [])

  useEffect(() => {
    const userChanged = previousUser.current !== user.id
    previousUser.current = user.id
    if (userChanged) {
      generation.current += 1
      controller.current?.abort()
      request.current = null
      setState({ kind: 'loading' })
    }
    if (user.role !== 'supervisor') {
      return
    }
    void refresh(userChanged)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      generation.current += 1
      controller.current?.abort()
    }
  }, [refresh, user.id, user.role])

  return <SupervisorQueueContext.Provider value={{ state, refresh, remove }}>{children}</SupervisorQueueContext.Provider>
}
