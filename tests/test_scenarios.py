"""Deterministic reconciliation scenario transforms and API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.reconciliation import CSVLoader, ReconciliationEngine
from backend.app.workspace.scenarios import (
    SCENARIO_BANK_FILE,
    SCENARIO_DUPLICATE,
    SCENARIO_NORMAL,
    SCENARIO_REFUND_SPIKE,
    SCENARIO_SETTLEMENT_DELAY,
    apply_scenario,
    parse_scenario,
)
from backend.app.workspace.store import WorkspaceStore

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
GENERATED_DIR = Path(__file__).resolve().parents[1] / "data" / "generated"

SCENARIOS = (
    SCENARIO_REFUND_SPIKE,
    SCENARIO_SETTLEMENT_DELAY,
    SCENARIO_DUPLICATE,
    SCENARIO_BANK_FILE,
)


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceStore:
    return WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=tmp_path / "runs",
        persist_runs=True,
    )


@pytest.fixture
def client(workspace: WorkspaceStore):
    app = create_app(workspace=workspace)
    with TestClient(app) as test_client:
        yield test_client, workspace


def _counts(body: dict) -> tuple[int, int, int, dict]:
    return (
        body["payments_processed"],
        body["reconciled_count"],
        body["exception_count"],
        dict(body["status_counts"]),
    )


def test_parse_scenario_defaults_and_rejects_unknown():
    assert parse_scenario(None) == SCENARIO_NORMAL
    assert parse_scenario("") == SCENARIO_NORMAL
    assert parse_scenario("Refund_Spike") == SCENARIO_REFUND_SPIKE
    with pytest.raises(ValueError, match="Unsupported scenario"):
        parse_scenario("solar_flare")


def test_apply_normal_does_not_change_engine_result():
    data = CSVLoader.load_all(SAMPLE_DIR)
    baseline = ReconciliationEngine(data).reconcile()
    transformed = apply_scenario(data, SCENARIO_NORMAL)
    again = ReconciliationEngine(transformed).reconcile()
    assert again.summary.status_counts == baseline.summary.status_counts
    assert again.summary.exception_count == baseline.summary.exception_count
    assert again.summary.payments_processed == baseline.summary.payments_processed


def test_each_scenario_is_deterministic_and_different_from_normal():
    data = CSVLoader.load_all(SAMPLE_DIR)
    normal = ReconciliationEngine(apply_scenario(data, SCENARIO_NORMAL)).reconcile()
    seen = {tuple(sorted(normal.summary.status_counts.items()))}

    for scenario in SCENARIOS:
        first = ReconciliationEngine(apply_scenario(data, scenario)).reconcile()
        second = ReconciliationEngine(apply_scenario(data, scenario)).reconcile()
        assert first.summary.status_counts == second.summary.status_counts
        assert first.summary.exception_count == second.summary.exception_count
        assert first.summary.exception_count > normal.summary.exception_count
        fingerprint = tuple(sorted(first.summary.status_counts.items()))
        assert fingerprint not in seen
        seen.add(fingerprint)


def test_post_omitted_scenario_is_normal(client):
    test_client, _ = client
    body = test_client.post("/api/runs").json()
    assert body["scenario"] == SCENARIO_NORMAL


def test_post_unknown_scenario_is_400(client):
    test_client, _ = client
    response = test_client.post("/api/runs", json={"scenario": "not-a-scenario"})
    assert response.status_code == 400
    assert "Unsupported scenario" in response.json()["detail"]


def test_repeated_scenario_runs_share_results_not_ids(client):
    test_client, _ = client
    first = test_client.post("/api/runs", json={"scenario": SCENARIO_REFUND_SPIKE})
    second = test_client.post("/api/runs", json={"scenario": SCENARIO_REFUND_SPIKE})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run_id"] != second.json()["run_id"]
    assert _counts(first.json()) == _counts(second.json())
    assert first.json()["scenario"] == SCENARIO_REFUND_SPIKE
    assert test_client.get("/api/runs").json()[-1]["scenario"] == SCENARIO_REFUND_SPIKE


def test_scenario_run_is_restored_after_restart(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    writer = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=writer)) as first_client:
        created = first_client.post(
            "/api/runs", json={"scenario": SCENARIO_SETTLEMENT_DELAY}
        )
        assert created.status_code == 200
        original = created.json()

    restored = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=restored)) as test_client:
        current = test_client.get("/api/runs/current")
        assert current.status_code == 200
        body = current.json()
        assert body["run_id"] == original["run_id"]
        assert body["scenario"] == SCENARIO_SETTLEMENT_DELAY
        assert body["exception_count"] == original["exception_count"]
        assert body["status_counts"] == original["status_counts"]
        assert test_client.get("/api/payments").status_code == 200
        assert test_client.get("/api/investigations").status_code == 200


@pytest.mark.skipif(
    not (GENERATED_DIR / "payments.csv").is_file(),
    reason="generated 1,000-payment dataset is not present",
)
def test_generated_normal_and_scenario_bands():
    data = CSVLoader.load_all(GENERATED_DIR)
    normal = ReconciliationEngine(apply_scenario(data, SCENARIO_NORMAL)).reconcile()
    assert normal.summary.payments_processed == 1000
    assert normal.summary.reconciled_count == 980
    assert normal.summary.exception_count == 20

    refund = ReconciliationEngine(
        apply_scenario(data, SCENARIO_REFUND_SPIKE)
    ).reconcile()
    delay = ReconciliationEngine(
        apply_scenario(data, SCENARIO_SETTLEMENT_DELAY)
    ).reconcile()
    duplicate = ReconciliationEngine(
        apply_scenario(data, SCENARIO_DUPLICATE)
    ).reconcile()
    bank = ReconciliationEngine(apply_scenario(data, SCENARIO_BANK_FILE)).reconcile()

    assert 30 <= refund.summary.exception_count <= 40
    assert 50 <= delay.summary.exception_count <= 60
    assert 40 <= duplicate.summary.exception_count <= 50
    assert 50 <= bank.summary.exception_count <= 70
    assert refund.summary.status_counts.get("REFUND_MISMATCH", 0) > 5
    assert delay.summary.status_counts.get("MISSING_SETTLEMENT", 0) > 5
    assert duplicate.summary.status_counts.get("DUPLICATE", 0) > 5
    assert bank.summary.status_counts.get("UNMATCHED_REFERENCE", 0) > 5
