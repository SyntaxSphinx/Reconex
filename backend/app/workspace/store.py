"""In-process workspace: loaded CSVs, current run/report, and run history."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.api.schemas import (
    AnalyticsWorkspaceResponse,
    CurrentRunResponse,
    HealthPoint,
    InvestigationBundleResponse,
    PaymentResponse,
)
from backend.app.investigation.config import InvestigatorConfig
from backend.app.investigation.context import InvestigationContextBuilder
from backend.app.investigation.investigator import AIInvestigator
from backend.app.investigation.models import InvestigationRecord, InvestigationReport
from backend.app.investigation.provider import LLMProviderError, OpenAICompatibleProvider
from backend.app.reconciliation.engine import ReconciliationEngine
from backend.app.reconciliation.loader import CSVLoader, LoadedData
from backend.app.reconciliation.models import ReconciliationResult, ReconciliationRun

from .paths import resolve_data_dir, resolve_runs_dir
from .projections import (
    allocate_run_id,
    analytics_workspace,
    current_run_response,
    eligible_results,
    health_point,
    investigation_bundle,
    investigation_report_from_records,
    payment_results_by_id,
    project_payment,
)
from .scenarios import SCENARIO_NORMAL, apply_scenario, parse_scenario

logger = logging.getLogger(__name__)


class WorkspaceStore:
    """Process-local state for the API layer.

    Does not run reconciliation or investigation on construction.
    """

    def __init__(
        self,
        data_dir: Path,
        runs_dir: Optional[Path] = None,
        persist_runs: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.runs_dir = Path(runs_dir) if runs_dir is not None else resolve_runs_dir()
        self.persist_runs = persist_runs

        self.loaded_data: Optional[LoadedData] = None
        self.current_data: Optional[LoadedData] = None
        self.current_run: Optional[ReconciliationRun] = None
        self.current_report: Optional[InvestigationReport] = None
        self.run_history: list[HealthPoint] = []
        self.current_run_id: Optional[str] = None
        self.current_scenario: str = SCENARIO_NORMAL

    @classmethod
    def from_env(cls) -> "WorkspaceStore":
        return cls(data_dir=resolve_data_dir(), runs_dir=resolve_runs_dir())

    def load_data(self, *, force: bool = False) -> LoadedData:
        """Load CSVs once and reuse them until force=True."""
        if self.loaded_data is None or force:
            logger.info("Loading CSVs from %s", self.data_dir)
            self.loaded_data = CSVLoader.load_all(self.data_dir)
        return self.loaded_data

    def restore_persisted_runs(self) -> None:
        """Restore run_history and current_run from JSON on disk.

        Does not execute ReconciliationEngine or call the LLM. Safe to call when
        data/runs/ is missing or empty. Skips unreadable files without failing.
        """
        if self.current_run is not None or self.run_history:
            return

        if not self.runs_dir.is_dir():
            return

        restored: list[tuple[datetime, str, HealthPoint, ReconciliationRun]] = []
        for path in sorted(self.runs_dir.glob("*.json")):
            loaded = self._load_persisted_run_file(path)
            if loaded is None:
                continue
            run_id, health, run = loaded
            restored.append((run.summary.run_timestamp, run_id, health, run))

        if not restored:
            return

        restored.sort(key=lambda item: (item[0], item[1]))
        self.run_history = [health for _, _, health, _ in restored]
        _, run_id, health, run = restored[-1]
        self.current_run = run
        self.current_run_id = run_id
        self.current_scenario = health.scenario or SCENARIO_NORMAL
        self.current_report = None
        if self.loaded_data is not None:
            self.current_data = apply_scenario(self.loaded_data, self.current_scenario)
        logger.info(
            "Restored %s persisted run(s); current_run=%s scenario=%s",
            len(restored),
            run_id,
            self.current_scenario,
        )

    def active_data(self) -> LoadedData:
        """CSV snapshot used for the current run (scenario-transformed when set)."""
        if self.current_data is not None:
            return self.current_data
        if self.loaded_data is None:
            raise RuntimeError("No reconciliation run has been executed")
        return self.loaded_data

    def run_reconciliation(self, scenario: str = SCENARIO_NORMAL) -> CurrentRunResponse:
        """Run the existing engine, store the result, and append one health point."""
        key = parse_scenario(scenario)
        base = self.load_data()
        data = apply_scenario(base, key)
        run = ReconciliationEngine(data).reconcile()

        run_id = allocate_run_id(
            run.summary.run_timestamp,
            {point.run_id for point in self.run_history},
        )
        snapshot = health_point(run_id, run, scenario=key)

        self.current_data = data
        self.current_run = run
        self.current_run_id = run_id
        self.current_scenario = key
        self.current_report = None
        self.run_history.append(snapshot)

        if self.persist_runs:
            self._persist_run(run_id, run, key)

        return current_run_response(run_id, run, scenario=key)

    def current_summary(self) -> Optional[CurrentRunResponse]:
        if self.current_run is None or self.current_run_id is None:
            return None
        return current_run_response(
            self.current_run_id, self.current_run, scenario=self.current_scenario
        )

    def has_current_run(self) -> bool:
        return self.current_run is not None and self.loaded_data is not None

    def list_payments(self) -> list[PaymentResponse]:
        if self.current_run is None:
            raise RuntimeError("No reconciliation run has been executed")
        data = self.active_data()
        results = payment_results_by_id(self.current_run)
        return [
            project_payment(payment, results.get(payment.payment_id))
            for payment in data.payments
        ]

    def get_payment(self, payment_id: str) -> Optional[PaymentResponse]:
        if self.current_run is None:
            raise RuntimeError("No reconciliation run has been executed")
        data = self.active_data()
        payment = next(
            (
                item
                for item in data.payments
                if item.payment_id == payment_id
            ),
            None,
        )
        if payment is None:
            return None
        return project_payment(
            payment, payment_results_by_id(self.current_run).get(payment_id)
        )

    def list_investigations(self) -> list[InvestigationBundleResponse]:
        if self.current_run is None:
            raise RuntimeError("No reconciliation run has been executed")
        builder = InvestigationContextBuilder(data=self.active_data())
        stored = {
            record.exception_id: record
            for record in (self.current_report.records if self.current_report else [])
        }
        bundles: list[InvestigationBundleResponse] = []
        for result in eligible_results(self.current_run):
            context = builder.build(result)
            bundles.append(
                investigation_bundle(result, context, stored.get(context.exception_id))
            )
        return bundles

    def get_investigation(self, exception_id: str) -> Optional[InvestigationBundleResponse]:
        for bundle in self.list_investigations():
            if bundle.record.exception_id == exception_id:
                return bundle
        return None

    def get_analytics(self) -> AnalyticsWorkspaceResponse:
        if self.current_run is None or self.loaded_data is None:
            raise RuntimeError("No reconciliation run has been executed")
        records = [bundle.record for bundle in self.list_investigations()]
        return analytics_workspace(
            self.current_run, self.run_history, records
        )

    def get_investigation_report(self) -> InvestigationReport:
        if self.current_run is None or self.loaded_data is None:
            raise RuntimeError("No reconciliation run has been executed")
        if self.current_report is not None:
            return self.current_report
        records = [bundle.record for bundle in self.list_investigations()]
        return investigation_report_from_records(self.current_run, records)

    def run_ai_investigation(self, exception_id: str) -> InvestigationRecord:
        """Run AI investigation on a single exception and store the result.

        Raises:
            RuntimeError: No reconciliation run available
            ValueError: Exception ID not found or not eligible
            LLMProviderError: LLM provider failure (API key missing, timeout, etc.)
        """
        if self.current_run is None:
            raise RuntimeError("No reconciliation run has been executed")

        # Find the reconciliation result for this exception
        result: ReconciliationResult | None = None
        for r in eligible_results(self.current_run):
            builder = InvestigationContextBuilder(data=self.active_data())
            context = builder.build(r)
            if context.exception_id == exception_id:
                result = r
                break

        if result is None:
            raise ValueError(
                f"Exception {exception_id} not found or not eligible for AI investigation"
            )

        # Initialize investigator with current config
        config = InvestigatorConfig.from_env()
        provider = OpenAICompatibleProvider(config)
        investigator = AIInvestigator(provider, config)
        builder = InvestigationContextBuilder(data=self.active_data())

        # Investigate this single result
        record = investigator.investigate_result(result, builder)

        # Initialize report if needed
        if self.current_report is None:
            self.current_report = InvestigationReport(records=[])

        # Update or append the record
        existing_idx = next(
            (
                i
                for i, r in enumerate(self.current_report.records)
                if r.exception_id == exception_id
            ),
            None,
        )
        if existing_idx is not None:
            self.current_report.records[existing_idx] = record
        else:
            self.current_report.records.append(record)

        return record

    def _persist_run(
        self, run_id: str, run: ReconciliationRun, scenario: str = SCENARIO_NORMAL
    ) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{run_id}.json"
        payload = {
            "run_id": run_id,
            "scenario": scenario,
            "health": health_point(run_id, run, scenario=scenario).model_dump(),
            "run": run.model_dump(mode="json"),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Persisted run %s to %s", run_id, path)

    def _load_persisted_run_file(
        self, path: Path
    ) -> Optional[tuple[str, HealthPoint, ReconciliationRun]]:
        """Parse one persisted run file. Returns None when the file is unusable."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable run file %s: %s", path, exc)
            return None

        if not isinstance(payload, dict):
            logger.warning("Skipping run file %s: expected a JSON object", path)
            return None

        run_payload = payload.get("run")
        if not isinstance(run_payload, dict):
            logger.warning("Skipping run file %s: missing run payload", path)
            return None

        try:
            run = ReconciliationRun.model_validate(run_payload)
        except Exception as exc:  # pydantic ValidationError and similar
            logger.warning("Skipping invalid run file %s: %s", path, exc)
            return None

        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            run_id = path.stem

        health_payload = payload.get("health")
        scenario = payload.get("scenario")
        if not isinstance(scenario, str) or not scenario.strip():
            if isinstance(health_payload, dict) and isinstance(
                health_payload.get("scenario"), str
            ):
                scenario = health_payload["scenario"]
            else:
                scenario = SCENARIO_NORMAL

        if isinstance(health_payload, dict):
            try:
                health = HealthPoint.model_validate(health_payload)
            except Exception as exc:
                logger.warning(
                    "Using rebuilt health for %s; stored health invalid: %s",
                    path,
                    exc,
                )
                health = health_point(run_id, run, scenario=scenario)
        else:
            health = health_point(run_id, run, scenario=scenario)

        if health.run_id != run_id or health.scenario != scenario:
            health = health.model_copy(update={"run_id": run_id, "scenario": scenario})

        return run_id, health, run
