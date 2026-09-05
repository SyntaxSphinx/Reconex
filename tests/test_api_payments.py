"""API tests for projected payment endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.investigation.context import exception_id_for, is_eligible
from backend.app.main import create_app
from backend.app.workspace.projections import map_payment_status, project_payment
from backend.app.workspace.store import WorkspaceStore

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceStore:
    return WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=tmp_path / "runs",
        persist_runs=False,
    )


@pytest.fixture
def client(workspace: WorkspaceStore):
    app = create_app(workspace=workspace)
    with TestClient(app) as test_client:
        yield test_client, workspace


def test_list_payments_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/payments")
    assert response.status_code == 409
    assert response.json()["detail"] == "No reconciliation run has been executed"


def test_get_payment_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/payments/pay_missing")
    assert response.status_code == 409


def test_list_and_detail_after_run(client):
    test_client, workspace = client
    created = test_client.post("/api/runs")
    assert created.status_code == 200

    listed = test_client.get("/api/payments")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == len(workspace.loaded_data.payments)
    assert len(rows) == len(workspace.current_run.payment_results)

    first = rows[0]
    assert first["payment_id"]
    assert first["order_id"]
    assert isinstance(first["amount_paise"], int)
    assert first["currency"]
    assert first["payment_date"]
    assert first["payment_status"] in {"authorized", "captured", "refunded", "failed"}
    assert first["reconciliation_status"]
    assert first["incident_ids"] == []
    assert "result_summary" in first
    assert "investigation_id" in first

    source = next(
        payment
        for payment in workspace.loaded_data.payments
        if payment.payment_id == first["payment_id"]
    )
    result = next(
        item
        for item in workspace.current_run.payment_results
        if item.evidence.payment_id == first["payment_id"]
    )
    expected = project_payment(source, result)
    assert first == expected.model_dump()
    assert first["payment_status"] == map_payment_status(source)
    if is_eligible(result):
        assert first["investigation_id"] == exception_id_for(result)
    else:
        assert first["investigation_id"] is None

    detail = test_client.get(f"/api/payments/{first['payment_id']}")
    assert detail.status_code == 200
    assert detail.json() == first


def test_unknown_payment_id_is_404(client):
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200
    response = test_client.get("/api/payments/pay_does_not_exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"
