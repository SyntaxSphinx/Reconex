import { useCallback, useState, type ReactNode } from 'react'
import { WorkspaceRefreshContext } from './workspaceRefreshContext'

export function WorkspaceRefreshProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0)
  const refresh = useCallback(() => setTick((value) => value + 1), [])
  return (
    <WorkspaceRefreshContext.Provider value={{ tick, refresh }}>
      {children}
    </WorkspaceRefreshContext.Provider>
  )
}
