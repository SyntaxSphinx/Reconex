import { useEffect, useState } from 'react'
import { overviewRepository } from '../data/overview/overviewRepository'
import type { CurrentRun } from '../types/overview'
import { useWorkspaceRefresh } from './useWorkspaceRefresh'

export function useCurrentRun() {
  const { tick } = useWorkspaceRefresh()
  const [run, setRun] = useState<CurrentRun | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    overviewRepository
      .getCurrentRun()
      .then((next) => {
        if (!cancelled) setRun(next)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load current run')
        setRun(null)
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { run, error }
}
