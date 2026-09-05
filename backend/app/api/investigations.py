"""Investigation bundle endpoints. Context comes from InvestigationContextBuilder."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.deps import get_workspace
from backend.app.api.schemas import InvestigationBundleResponse
from backend.app.investigation.models import InvestigationRecord, InvestigationReport
from backend.app.investigation.provider import LLMProviderError

router = APIRouter(tags=["investigations"])

_NO_RUN = "No reconciliation run has been executed"


@router.get("/api/investigations", response_model=list[InvestigationBundleResponse])
def list_investigations(request: Request) -> list[InvestigationBundleResponse]:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    return workspace.list_investigations()


@router.get("/api/investigations/report", response_model=InvestigationReport)
def get_investigation_report(request: Request) -> InvestigationReport:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    return workspace.get_investigation_report()


@router.get("/api/investigations/{exception_id}", response_model=InvestigationBundleResponse)
def get_investigation(exception_id: str, request: Request) -> InvestigationBundleResponse:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    bundle = workspace.get_investigation(exception_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return bundle


@router.post("/api/investigations/{exception_id}/run-ai", response_model=InvestigationRecord)
def run_ai_investigation(exception_id: str, request: Request) -> InvestigationRecord:
    """Run AI investigation on a single exception.

    Requires RECONEX_LLM_API_KEY environment variable. Investigation result is
    stored in workspace state and returned by subsequent GET requests.

    Returns:
        InvestigationRecord with AI finding, confidence, evidence, recommendation

    Raises:
        409: No reconciliation run available
        404: Exception not found or not eligible for AI investigation
        503: LLM provider error (missing API key, timeout, network failure)
    """
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)

    try:
        record = workspace.run_ai_investigation(exception_id)
        return record
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI investigation failed: {exc}. Check RECONEX_LLM_API_KEY is set.",
        ) from exc
