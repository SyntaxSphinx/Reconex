import { createContext } from 'react'

export type WorkspaceRefreshValue = {
  tick: number
  refresh: () => void
}

export const WorkspaceRefreshContext = createContext<WorkspaceRefreshValue>({
  tick: 0,
  refresh: () => {},
})
