"""API tests for workspace loading and reconciliation run endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.reconciliation import CSVLoader, ReconciliationEngine
from backend.app.workspace.paths import resolve_data_dir
from backend.app.workspace.projections import percent, reconciliation_rate
from backend.app.workspace.store import WorkspaceStore

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


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


def test_health_still_works(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "Reconex"


def test_startup_loads_csvs_but_does_not_reconcile(client):
    test_client, workspace = client
    assert workspace.loaded_data is not None
    assert workspace.current_run is None
    assert workspace.current_report is None
    assert workspace.run_history == []
    assert test_client.get("/api/runs").json() == []
    assert test_client.get("/api/runs/current").status_code == 404


def test_post_run_uses_engine_and_appends_history(client):
    test_client, workspace = client
    engine_run = ReconciliationEngine(CSVLoader.load_all(SAMPLE_DIR)).reconcile()

    created = test_client.post("/api/runs")
    assert created.status_code == 200
    body = created.json()

    assert body["payments_processed"] == engine_run.summary.payments_processed
    assert body["reconciled_count"] == engine_run.summary.reconciled_count
    assert body["pending_count"] == engine_run.summary.pending_count
    assert body["exception_count"] == engine_run.summary.exception_count
    assert body["status_counts"] == engine_run.summary.status_counts
    assert body["reconciliation_rate"] == reconciliation_rate(
        engine_run.summary.reconciled_count,
        engine_run.summary.payments_processed,
    )
    assert body["reconciled_percent"] == percent(
        engine_run.summary.reconciled_count,
        engine_run.summary.payments_processed,
    )
    assert workspace.current_run is not None
    assert workspace.current_report is None
    assert body["scenario"] == "normal"
    assert len(workspace.run_history) == 1

    history = test_client.get("/api/runs")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["run_id"] == body["run_id"]
    assert history.json()[0]["payments_processed"] == body["payments_processed"]
    assert history.json()[0]["scenario"] == "normal"

    current = test_client.get("/api/runs/current")
    assert current.status_code == 200
    assert current.json() == body

    persisted = list((workspace.runs_dir).glob(f"{body['run_id']}.json"))
    assert len(persisted) == 1


def test_second_post_appends_another_history_point(client):
    test_client, workspace = client
    first = test_client.post("/api/runs")
    second = test_client.post("/api/runs")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run_id"] != second.json()["run_id"]
    assert len(test_client.get("/api/runs").json()) == 2
    assert test_client.get("/api/runs/current").json()["run_id"] == second.json()["run_id"]
    assert workspace.current_report is None


def test_startup_with_missing_runs_dir_leaves_empty_workspace(tmp_path: Path):
    workspace = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=tmp_path / "does-not-exist",
        persist_runs=False,
    )
    app = create_app(workspace=workspace)
    with TestClient(app) as test_client:
        assert workspace.current_run is None
        assert workspace.run_history == []
        assert test_client.get("/api/runs").json() == []
        assert test_client.get("/api/runs/current").status_code == 404


def test_startup_restores_one_persisted_run(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    writer = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=writer)) as first_client:
        created = first_client.post("/api/runs")
        assert created.status_code == 200
        run_id = created.json()["run_id"]

    restored = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=restored)) as test_client:
        assert restored.current_run is not None
        assert restored.current_run_id == run_id
        assert len(restored.run_history) == 1
        assert restored.current_report is None

        current = test_client.get("/api/runs/current")
        assert current.status_code == 200
        assert current.json()["run_id"] == run_id

        history = test_client.get("/api/runs").json()
        assert len(history) == 1
        assert history[0]["run_id"] == run_id

        assert test_client.get("/api/payments").status_code == 200
        assert test_client.get("/api/investigations").status_code == 200
        assert test_client.get("/api/analytics").status_code == 200


def test_startup_restores_multiple_runs_chronologically(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    writer = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=writer)) as first_client:
        first = first_client.post("/api/runs")
        second = first_client.post("/api/runs")
        assert first.status_code == 200
        assert second.status_code == 200
        first_id = first.json()["run_id"]
        second_id = second.json()["run_id"]

    restored = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=restored)) as test_client:
        history = test_client.get("/api/runs").json()
        assert [point["run_id"] for point in history] == [first_id, second_id]
        assert test_client.get("/api/runs/current").json()["run_id"] == second_id
        assert restored.current_run_id == second_id


def test_startup_skips_malformed_run_files(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "broken.json").write_text("{not-json", encoding="utf-8")
    (runs_dir / "empty-object.json").write_text("{}", encoding="utf-8")
    (runs_dir / "not-an-object.json").write_text("[1, 2]", encoding="utf-8")

    writer = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=writer)) as first_client:
        created = first_client.post("/api/runs")
        assert created.status_code == 200
        run_id = created.json()["run_id"]

    restored = WorkspaceStore(
        data_dir=SAMPLE_DIR,
        runs_dir=runs_dir,
        persist_runs=True,
    )
    with TestClient(create_app(workspace=restored)) as test_client:
        assert restored.current_run_id == run_id
        assert len(restored.run_history) == 1
        assert test_client.get("/api/runs/current").json()["run_id"] == run_id


def test_resolve_data_dir_prefers_generated(tmp_path: Path):
    generated = tmp_path / "data" / "generated"
    sample = tmp_path / "data" / "sample"
    generated.mkdir(parents=True)
    sample.mkdir(parents=True)
    (generated / "payments.csv").write_text("payment_id\n", encoding="utf-8")
    (sample / "payments.csv").write_text("payment_id\n", encoding="utf-8")
    assert resolve_data_dir(env={}, root=tmp_path) == generated


def test_resolve_data_dir_falls_back_to_sample(tmp_path: Path):
    sample = tmp_path / "data" / "sample"
    sample.mkdir(parents=True)
    (sample / "payments.csv").write_text("payment_id\n", encoding="utf-8")
    assert resolve_data_dir(env={}, root=tmp_path) == sample


def test_resolve_data_dir_env_override(tmp_path: Path):
    custom = tmp_path / "custom-data"
    custom.mkdir()
    assert resolve_data_dir(env={"RECONEX_DATA_DIR": str(custom)}, root=tmp_path) == custom
