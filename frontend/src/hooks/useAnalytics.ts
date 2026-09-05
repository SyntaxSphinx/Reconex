import { useEffect, useState } from 'react'
import { analyticsRepository } from '../data/analytics/analyticsRepository'
import type { AnalyticsWorkspace } from '../types/analytics'
import { useWorkspaceRefresh } from './useWorkspaceRefresh'

export function useAnalyticsWorkspace() {
  const { tick } = useWorkspaceRefresh()
  const [workspace, setWorkspace] = useState<AnalyticsWorkspace | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    analyticsRepository
      .getWorkspace()
      .then((next) => {
        if (!cancelled) setWorkspace(next)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof Error ? err.message : 'Unable to load analytics',
        )
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { workspace, error }
}
