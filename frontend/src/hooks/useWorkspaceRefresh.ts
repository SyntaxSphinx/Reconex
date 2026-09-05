import { useContext } from 'react'
import { WorkspaceRefreshContext } from '../workspaceRefreshContext'

export function useWorkspaceRefresh() {
  return useContext(WorkspaceRefreshContext)
}
