import { useEffect, useState } from 'react'
import { overviewRepository } from '../data/overview/overviewRepository'
import type { ReconciliationHealthPoint } from '../types/overview'
import { useWorkspaceRefresh } from './useWorkspaceRefresh'

export function useReconciliationHealth() {
  const { tick } = useWorkspaceRefresh()
  const [points, setPoints] = useState<ReconciliationHealthPoint[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    overviewRepository
      .getReconciliationHealth()
      .then((next) => {
        if (!cancelled) setPoints(next)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load reconciliation health')
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { points, error }
}
