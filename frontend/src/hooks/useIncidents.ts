import { useEffect, useState } from 'react'
import { incidentRepository } from '../data/incidents/incidentRepository'
import type { Incident } from '../types/incident'

export function useIncidentList() {
  const [items, setItems] = useState<Incident[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    incidentRepository
      .list()
      .then((nextItems) => {
        if (!cancelled) setItems(nextItems)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load incidents')
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { items, error }
}

type IncidentQuery = {
  incidentId: string
  incident: Incident | null
  error: string | null
}

export function useIncident(incidentId: string | undefined) {
  const [query, setQuery] = useState<IncidentQuery | null>(null)

  useEffect(() => {
    if (!incidentId) return

    let cancelled = false

    incidentRepository
      .getById(incidentId)
      .then((result) => {
        if (!cancelled) {
          setQuery({ incidentId, incident: result, error: null })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setQuery({
          incidentId,
          incident: null,
          error: err instanceof Error ? err.message : 'Unable to load incident',
        })
      })

    return () => {
      cancelled = true
    }
  }, [incidentId])

  if (!incidentId) {
    return { incident: null, error: null }
  }

  if (query?.incidentId !== incidentId) {
    return { incident: undefined, error: null }
  }

  return { incident: query.incident, error: query.error }
}
