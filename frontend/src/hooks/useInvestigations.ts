import { useEffect, useState } from 'react'
import { investigationRepository } from '../data/investigations/investigationRepository'
import type { InvestigationBundle } from '../types/investigation'
import { useWorkspaceRefresh } from './useWorkspaceRefresh'

export function useInvestigationList() {
  const { tick } = useWorkspaceRefresh()
  const [items, setItems] = useState<InvestigationBundle[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    investigationRepository
      .list()
      .then((nextItems) => {
        if (cancelled) return
        setItems(nextItems)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load investigations')
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { items, error }
}

type InvestigationQuery = {
  exceptionId: string
  bundle: InvestigationBundle | null
  error: string | null
}

export function useInvestigation(exceptionId: string | undefined) {
  const { tick } = useWorkspaceRefresh()
  const [query, setQuery] = useState<InvestigationQuery | null>(null)

  useEffect(() => {
    if (!exceptionId) return

    let cancelled = false

    investigationRepository
      .getByExceptionId(exceptionId)
      .then((result) => {
        if (!cancelled) {
          setQuery({ exceptionId, bundle: result, error: null })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setQuery({
          exceptionId,
          bundle: null,
          error: err instanceof Error ? err.message : 'Unable to load investigation',
        })
      })

    return () => {
      cancelled = true
    }
  }, [exceptionId, tick])

  if (!exceptionId) {
    return { bundle: null, error: null }
  }

  if (query?.exceptionId !== exceptionId) {
    return { bundle: undefined, error: null }
  }

  return { bundle: query.bundle, error: query.error }
}
