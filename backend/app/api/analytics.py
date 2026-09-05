"""Analytics workspace. Projects stored runs; does not invent history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.deps import get_workspace
from backend.app.api.schemas import AnalyticsWorkspaceResponse

router = APIRouter(tags=["analytics"])

_NO_RUN = "No reconciliation run has been executed"


@router.get("/api/analytics", response_model=AnalyticsWorkspaceResponse)
def get_analytics(request: Request) -> AnalyticsWorkspaceResponse:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    return workspace.get_analytics()
