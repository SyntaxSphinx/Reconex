"""Reconciliation run endpoints. Handlers call the workspace, not the engine rules."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.schemas import CreateRunRequest, CurrentRunResponse, HealthPoint
from backend.app.reconciliation.loader import CSVLoadError
from backend.app.workspace.scenarios import UnknownScenarioError, parse_scenario
from backend.app.workspace.store import WorkspaceStore

router = APIRouter(tags=["runs"])


def _workspace(request: Request) -> WorkspaceStore:
    return request.app.state.workspace


@router.post("/api/runs", response_model=CurrentRunResponse)
def create_run(
    request: Request, body: CreateRunRequest | None = None
) -> CurrentRunResponse:
    """Execute ReconciliationEngine.reconcile() on the loaded CSVs."""
    try:
        scenario = parse_scenario(body.scenario if body else None)
        return _workspace(request).run_reconciliation(scenario)
    except UnknownScenarioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CSVLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/runs", response_model=list[HealthPoint])
def list_runs(request: Request) -> list[HealthPoint]:
    """Return stored run history only. Empty until POST /api/runs has been called."""
    return _workspace(request).run_history


@router.get("/api/runs/current", response_model=CurrentRunResponse)
def get_current_run(request: Request) -> CurrentRunResponse:
    summary = _workspace(request).current_summary()
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No reconciliation run has been executed",
        )
    return summary
