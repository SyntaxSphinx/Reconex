"""API tests for investigation bundle endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.investigation.context import (
    ELIGIBLE_STATUSES,
    InvestigationContextBuilder,
    exception_id_for,
    is_eligible,
)
from backend.app.investigation.models import InvestigationOutcome
from backend.app.main import create_app
from backend.app.workspace.projections import (
    deterministic_investigation_record,
    eligible_results,
    investigation_report_from_records,
)
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


def test_list_investigations_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/investigations")
    assert response.status_code == 409
    assert response.json()["detail"] == "No reconciliation run has been executed"


def test_get_investigation_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/investigations/EXC-PAYMENT-missing")
    assert response.status_code == 409


def test_report_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/investigations/report")
    assert response.status_code == 409
    assert response.json()["detail"] == "No reconciliation run has been executed"


def test_list_and_detail_after_run(client):
    test_client, workspace = client
    assert test_client.post("/api/runs").status_code == 200

    expected_results = eligible_results(workspace.current_run)
    builder = InvestigationContextBuilder(data=workspace.loaded_data)

    listed = test_client.get("/api/investigations")
    assert listed.status_code == 200
    bundles = listed.json()
    assert len(bundles) == len(expected_results)
    assert bundles

    first = bundles[0]
    assert first["record"]["exception_id"]
    assert first["record"]["deterministic_status"] in {
        status.value for status in ELIGIBLE_STATUSES
    }
    assert first["record"]["outcome"] == InvestigationOutcome.ESCALATED.value
    assert first["record"]["investigation"] is None
    assert first["record"]["human_review_required"] is True
    assert first["record"]["guardrail_violations"] == []
    assert first["record"]["failure_reason"] is None
    assert first["context"]["exception_id"] == first["record"]["exception_id"]
    assert first["context"]["evidence"]

    matching = next(
        result
        for result in expected_results
        if exception_id_for(result) == first["record"]["exception_id"]
    )
    expected = deterministic_investigation_record(
        matching, builder.build(matching)
    ).model_dump(mode="json")
    assert first["record"] == expected

    detail = test_client.get(f"/api/investigations/{first['record']['exception_id']}")
    assert detail.status_code == 200
    assert detail.json() == first


def test_report_after_run_uses_deterministic_records(client):
    test_client, workspace = client
    assert test_client.post("/api/runs").status_code == 200

    bundles = test_client.get("/api/investigations").json()
    builder = InvestigationContextBuilder(data=workspace.loaded_data)
    records = [
        deterministic_investigation_record(result, builder.build(result))
        for result in eligible_results(workspace.current_run)
    ]
    expected = investigation_report_from_records(
        workspace.current_run, records
    ).model_dump(mode="json")

    response = test_client.get("/api/investigations/report")
    assert response.status_code == 200
    body = response.json()
    assert body == expected
    assert body["eligible_exceptions"] == len(bundles)
    assert body["investigated"] == 0
    assert body["escalated"] == len(bundles)
    assert body["failed"] == 0
    assert body["human_review_required_count"] == len(bundles)
    assert body["financial_records_modified"] is False


def test_eligible_exception_id_returns_bundle(client):
    test_client, workspace = client
    assert test_client.post("/api/runs").status_code == 200
    result = eligible_results(workspace.current_run)[0]
    exception_id = exception_id_for(result)

    response = test_client.get(f"/api/investigations/{exception_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["record"]["exception_id"] == exception_id
    assert body["context"]["exception_id"] == exception_id
    assert is_eligible(result)


def test_non_eligible_exception_id_is_404(client):
    test_client, workspace = client
    assert test_client.post("/api/runs").status_code == 200
    ineligible = next(
        result
        for result in list(workspace.current_run.payment_results)
        + list(workspace.current_run.batch_results)
        if not is_eligible(result)
    )
    response = test_client.get(f"/api/investigations/{exception_id_for(ineligible)}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found"


def test_unknown_exception_id_is_404(client):
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200
    response = test_client.get("/api/investigations/EXC-PAYMENT-does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Investigation not found"


def test_payment_investigation_id_resolves_to_same_bundle(client):
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200

    payments = test_client.get("/api/payments").json()
    linked = next(payment for payment in payments if payment["investigation_id"])
    exception_id = linked["investigation_id"]

    bundle = test_client.get(f"/api/investigations/{exception_id}")
    assert bundle.status_code == 200
    body = bundle.json()
    assert body["record"]["exception_id"] == exception_id
    assert body["context"]["identifiers"]["payment_id"] == linked["payment_id"]
    assert body["record"]["investigation"] is None
    assert body["record"]["human_review_required"] is True


def test_run_ai_investigation_requires_run(client):
    test_client, _ = client
    response = test_client.post("/api/investigations/EXC-PAYMENT-missing/run-ai")
    assert response.status_code == 409
    assert response.json()["detail"] == "No reconciliation run has been executed"


def test_run_ai_investigation_unknown_exception_is_404(client):
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200
    response = test_client.post("/api/investigations/EXC-PAYMENT-does-not-exist/run-ai")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_run_ai_investigation_endpoint_exists(client):
    """Test that POST /api/investigations/{id}/run-ai endpoint exists and validates inputs."""
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200
    
    bundles = test_client.get("/api/investigations").json()
    exception_id = bundles[0]["record"]["exception_id"]
    
    # Endpoint exists and accepts valid exception IDs
    # Actual AI investigation requires RECONEX_LLM_API_KEY environment variable
    response = test_client.post(f"/api/investigations/{exception_id}/run-ai")
    # Returns either 200 (if API key exists) or 503 (if missing/failed)
    assert response.status_code in (200, 503)
