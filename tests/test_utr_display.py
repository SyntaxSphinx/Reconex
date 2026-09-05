"""Deterministic unique payment-facing UTR projection."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.reconciliation import CSVLoader, ReconciliationEngine
from backend.app.workspace.projections import project_payment
from backend.app.workspace.store import WorkspaceStore
from backend.app.workspace.utr_display import payment_facing_utr

GENERATED_DIR = Path(__file__).resolve().parents[1] / "data" / "generated"
SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def test_payment_facing_utr_is_deterministic_and_unique():
    base = "UTR202401033913368"
    first = payment_facing_utr("pay_216739_000000", base)
    second = payment_facing_utr("pay_246316_000001", base)
    assert first == payment_facing_utr("pay_216739_000000", base)
    assert first != second
    assert first is not None and first.startswith("UTR20240103")
    assert payment_facing_utr("pay_x", None) is None
    assert payment_facing_utr("pay_x", "") == ""
    assert payment_facing_utr("pay_x", "   ") == "   "


def test_projected_payments_have_unique_utrs_when_settled():
    data = CSVLoader.load_all(GENERATED_DIR if (GENERATED_DIR / "payments.csv").is_file() else SAMPLE_DIR)
    run = ReconciliationEngine(data).reconcile()
    by_id = {
        result.evidence.payment_id: result
        for result in run.payment_results
        if result.evidence.payment_id
    }
    projected = [
        project_payment(payment, by_id.get(payment.payment_id))
        for payment in data.payments
    ]
    with_utr = [row.settlement_utr for row in projected if row.settlement_utr]
    assert len(with_utr) >= 10
    assert len(with_utr) == len(set(with_utr))

    # Engine inputs are unchanged: raw settlement lines still share batch UTRs.
    raw = [
        line.settlement_utr
        for line in data.settlements
        if line.payment_id and (line.settlement_utr or "").strip()
    ]
    assert len(raw) > len(set(raw))


def test_api_payment_and_investigation_share_display_utr(tmp_path: Path):
    data_dir = GENERATED_DIR if (GENERATED_DIR / "payments.csv").is_file() else SAMPLE_DIR
    workspace = WorkspaceStore(
        data_dir=data_dir,
        runs_dir=tmp_path / "runs",
        persist_runs=False,
    )
    app = create_app(workspace=workspace)
    with TestClient(app) as client:
        assert client.post("/api/runs").status_code == 200
        payments = client.get("/api/payments").json()
        settled = [row for row in payments if row.get("settlement_utr")]
        assert len(settled) >= 2
        assert settled[0]["settlement_utr"] != settled[1]["settlement_utr"]

        target = next(
            row
            for row in payments
            if row.get("investigation_id") and row.get("settlement_utr")
        )
        detail = client.get(f"/api/payments/{target['payment_id']}").json()
        assert detail["settlement_utr"] == target["settlement_utr"]

        bundle = client.get(f"/api/investigations/{target['investigation_id']}").json()
        assert bundle["context"]["identifiers"]["payment_id"] == target["payment_id"]
        assert (
            bundle["context"]["identifiers"]["settlement_utr"]
            == target["settlement_utr"]
        )
