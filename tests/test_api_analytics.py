"""API tests for the analytics workspace projection."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.investigation.context import is_eligible
from backend.app.main import create_app
from backend.app.workspace.projections import ANALYTICS_EXCEPTION_TYPES
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


def test_analytics_conflict_without_run(client):
    test_client, _ = client
    response = test_client.get("/api/analytics")
    assert response.status_code == 409
    assert response.json()["detail"] == "No reconciliation run has been executed"


def test_analytics_after_run_uses_real_history_only(client):
    test_client, workspace = client
    created = test_client.post("/api/runs")
    assert created.status_code == 200
    run_body = created.json()

    response = test_client.get("/api/analytics")
    assert response.status_code == 200
    body = response.json()

    history = test_client.get("/api/runs").json()
    assert len(body["reconciliation"]) == 1
    assert len(body["exception_trend"]) == 1
    assert body["reconciliation"][0]["run_id"] == run_body["run_id"]
    assert body["reconciliation"][0]["reconciliation_rate"] == run_body["reconciliation_rate"]
    assert body["reconciliation"][0]["payments_processed"] == run_body["payments_processed"]
    assert body["as_of"] == run_body["run_date"]
    assert [point["run_id"] for point in body["reconciliation"]] == [
        point["run_id"] for point in history
    ]

    assert set(ANALYTICS_EXCEPTION_TYPES) <= {row["type"] for row in body["distribution"]}
    payment_exceptions = {
        status: count
        for status, count in workspace.current_run.summary.status_counts.items()
        if count > 0
        and status not in {"RECONCILED", "PENDING_SETTLEMENT", "PENDING_BANK_CREDIT"}
    }
    by_type = {row["type"]: row for row in body["distribution"]}
    assert sum(row["count"] for row in body["distribution"]) == (
        workspace.current_run.summary.exception_count
    )
    for status, count in payment_exceptions.items():
        assert by_type[status]["count"] == count
    amount_mismatch = by_type["AMOUNT_MISMATCH"]["count"]
    assert amount_mismatch == workspace.current_run.summary.status_counts.get(
        "AMOUNT_MISMATCH", 0
    )
    assert body["exception_trend"][0]["counts"]["AMOUNT_MISMATCH"] == amount_mismatch
    eligible = [
        result
        for result in list(workspace.current_run.payment_results)
        + list(workspace.current_run.batch_results)
        if is_eligible(result)
    ]
    assert len(body["investigations"]) == len(eligible)
    assert all(record["investigation"] is None for record in body["investigations"])


def test_analytics_second_run_appends_one_real_point(client):
    test_client, _ = client
    assert test_client.post("/api/runs").status_code == 200
    assert test_client.post("/api/runs").status_code == 200
    body = test_client.get("/api/analytics").json()
    assert len(body["reconciliation"]) == 2
    assert len(body["exception_trend"]) == 2
    assert body["reconciliation"][0]["run_id"] != body["reconciliation"][1]["run_id"]
