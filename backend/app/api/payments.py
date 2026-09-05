"""Payment projection endpoints. Join loaded CSVs with the current run."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.deps import get_workspace
from backend.app.api.schemas import PaymentResponse

router = APIRouter(tags=["payments"])

_NO_RUN = "No reconciliation run has been executed"


@router.get("/api/payments", response_model=list[PaymentResponse])
def list_payments(request: Request) -> list[PaymentResponse]:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    return workspace.list_payments()


@router.get("/api/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str, request: Request) -> PaymentResponse:
    workspace = get_workspace(request)
    if not workspace.has_current_run():
        raise HTTPException(status_code=409, detail=_NO_RUN)
    payment = workspace.get_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
