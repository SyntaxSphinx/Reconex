"""Independent evaluation of reconciliation results against Phase 1 ground truth."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from backend.app.models.anomaly import AnomalyRecord, AnomalyType
from backend.app.reconciliation import (
    CSVLoader,
    ReconciliationEngine,
    ReconciliationResult,
    ReconciliationRun,
    ReconciliationStatus,
    ResultLevel,
)
from .mapping import (
    DOWNSTREAM_RULES,
    EXPECTED_PRIMARY_STATUS,
    EXPECTED_RESULT_LEVEL,
)
from .models import (
    AnomalyEvaluation,
    DownstreamEffect,
    EngineResultRef,
    EvaluationReport,
    FalsePositive,
    IdentifierSet,
    OverallMetrics,
    TypeMetrics,
)


PENDING_STATUSES = {
    ReconciliationStatus.PENDING_SETTLEMENT,
    ReconciliationStatus.PENDING_BANK_CREDIT,
}

METRIC_DEFINITIONS = {
    "detection_rate": (
        "(correctly_detected + incorrectly_classified) / total_ground_truth_anomalies. "
        "Recall of matching a GT anomaly to a unique engine result, ignoring class."
    ),
    "classification_accuracy": (
        "correctly_detected / (correctly_detected + incorrectly_classified). "
        "Accuracy of the engine status among uniquely matched GT anomalies. "
        "None when no GT anomaly was matched."
    ),
    "exact_recall": (
        "correctly_detected / total_ground_truth_anomalies. "
        "Fraction of GT anomalies that were both uniquely matched and correctly classified."
    ),
    "false_positives": (
        "Engine exception results (not RECONCILED, not pending) that are neither a "
        "GT primary match nor a documented downstream effect."
    ),
    "missed_anomalies": (
        "GT anomalies that could not be uniquely bound to an engine result using "
        "strong identifiers (payment_id, order_id, settlement_id, settlement_utr, "
        "bank_transaction_id, entity_id)."
    ),
}


def load_ground_truth(path: Path) -> tuple[list[AnomalyRecord], Optional[int], Optional[int]]:
    """Load ground_truth.json. Returns (anomalies, seed, num_records)."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    anomalies = [AnomalyRecord.model_validate(item) for item in payload.get("anomalies", [])]
    return anomalies, payload.get("seed"), payload.get("num_records")


def result_to_ref(result: ReconciliationResult) -> EngineResultRef:
    ev = result.evidence
    return EngineResultRef(
        level=result.level,
        primary_status=result.primary_status,
        secondary_findings=list(result.secondary_findings),
        payment_id=ev.payment_id,
        order_id=ev.order_id,
        settlement_id=ev.settlement_id,
        settlement_utr=ev.settlement_utr,
        bank_transaction_id=ev.bank_transaction_id,
        settlement_entity_ids=list(ev.settlement_entity_ids),
        rule_applied=ev.rule_applied,
        expected_amount_paise=ev.expected_amount_paise,
        actual_amount_paise=ev.actual_amount_paise,
        variance_paise=ev.variance_paise,
    )


def is_exception(result: ReconciliationResult) -> bool:
    if result.primary_status == ReconciliationStatus.RECONCILED:
        return False
    if result.primary_status in PENDING_STATUSES:
        return False
    return True


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value).strip()
    return [text] if text else []


def identifiers_from_anomaly(anomaly: AnomalyRecord) -> IdentifierSet:
    rid = anomaly.related_ids or {}
    payment_id = rid.get("payment_id")
    if not payment_id and anomaly.affected_entity_type == "payment":
        payment_id = anomaly.affected_entity_id

    order_id = rid.get("order_id")

    settlement_ids = _as_str_list(rid.get("settlement_ids"))
    if rid.get("settlement_id"):
        settlement_ids = [str(rid["settlement_id"])] + [s for s in settlement_ids if s != str(rid["settlement_id"])]
    settlement_id = settlement_ids[0] if settlement_ids else None

    utr = rid.get("settlement_utr") or rid.get("original_utr")

    bank_id = (
        rid.get("bank_transaction_id")
        or rid.get("removed_bank_transaction_id")
        or rid.get("related_bank_transaction_id")
    )

    entity_id = (
        rid.get("entity_id")
        or rid.get("original_entity_id")
        or rid.get("duplicate_entity_id")
        or rid.get("refund_entity_id")
        or rid.get("removed_entity_id")
        or (anomaly.affected_entity_id if anomaly.affected_entity_type == "settlement" else None)
    )

    return IdentifierSet(
        payment_id=str(payment_id) if payment_id else None,
        order_id=str(order_id) if order_id else None,
        settlement_id=str(settlement_id) if settlement_id else None,
        settlement_utr=str(utr) if utr else None,
        bank_transaction_id=str(bank_id) if bank_id else None,
        entity_id=str(entity_id) if entity_id else None,
        match_keys=[],
    )


def _unique_or_none(candidates: list[ReconciliationResult]) -> tuple[Optional[ReconciliationResult], Optional[str]]:
    if len(candidates) == 1:
        return candidates[0], None
    if len(candidates) == 0:
        return None, "no candidate"
    return None, f"ambiguous ({len(candidates)} candidates)"


class _ResultIndex:
    def __init__(self, run: ReconciliationRun):
        self.payments = list(run.payment_results)
        self.batches = list(run.batch_results)
        self.payment_by_id: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.payment_by_order: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.payment_by_entity: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.batch_by_settlement: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.batch_by_utr: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.batch_by_bank: dict[str, list[ReconciliationResult]] = defaultdict(list)
        self.batch_by_line_utr: dict[str, list[ReconciliationResult]] = defaultdict(list)

        for result in self.payments:
            ev = result.evidence
            if ev.payment_id:
                self.payment_by_id[ev.payment_id].append(result)
            if ev.order_id:
                self.payment_by_order[ev.order_id].append(result)
            for entity_id in ev.settlement_entity_ids:
                self.payment_by_entity[entity_id].append(result)

        for result in self.batches:
            ev = result.evidence
            if ev.settlement_id:
                self.batch_by_settlement[ev.settlement_id].append(result)
            if ev.settlement_utr:
                self.batch_by_utr[ev.settlement_utr].append(result)
            if ev.bank_transaction_id:
                self.batch_by_bank[ev.bank_transaction_id].append(result)

        utr_to_settlements: dict[str, set[str]] = defaultdict(set)
        for result in self.payments:
            ev = result.evidence
            if ev.settlement_utr and ev.settlement_id:
                utr_to_settlements[ev.settlement_utr].add(ev.settlement_id)
        for utr, settlement_ids in utr_to_settlements.items():
            if len(settlement_ids) != 1:
                continue
            settlement_id = next(iter(settlement_ids))
            self.batch_by_line_utr[utr] = list(self.batch_by_settlement.get(settlement_id, []))

    def match_primary(
        self, anomaly: AnomalyRecord, ids: IdentifierSet
    ) -> tuple[Optional[ReconciliationResult], list[str], Optional[str]]:
        level = EXPECTED_RESULT_LEVEL[anomaly.anomaly_type]
        if level == ResultLevel.PAYMENT:
            return self._match_payment(ids)
        return self._match_batch(ids)

    def _match_payment(
        self, ids: IdentifierSet
    ) -> tuple[Optional[ReconciliationResult], list[str], Optional[str]]:
        if ids.payment_id:
            found, reason = _unique_or_none(self.payment_by_id.get(ids.payment_id, []))
            if found:
                return found, ["payment_id"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["payment_id"], reason
            return None, ["payment_id"], "payment_id did not match any engine result"

        if ids.entity_id:
            found, reason = _unique_or_none(self.payment_by_entity.get(ids.entity_id, []))
            if found:
                return found, ["entity_id"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["entity_id"], reason
            return None, ["entity_id"], "entity_id did not match any engine result"

        if ids.order_id:
            found, reason = _unique_or_none(self.payment_by_order.get(ids.order_id, []))
            if found:
                return found, ["order_id"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["order_id"], reason
            return None, ["order_id"], "order_id did not match any engine result"

        return None, [], "no unique payment-level identifier match"

    def _match_batch(
        self, ids: IdentifierSet
    ) -> tuple[Optional[ReconciliationResult], list[str], Optional[str]]:
        if ids.settlement_id:
            found, reason = _unique_or_none(self.batch_by_settlement.get(ids.settlement_id, []))
            if found:
                return found, ["settlement_id"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["settlement_id"], reason
            return None, ["settlement_id"], "settlement_id did not match any engine result"

        if ids.bank_transaction_id:
            found, reason = _unique_or_none(self.batch_by_bank.get(ids.bank_transaction_id, []))
            if found:
                return found, ["bank_transaction_id"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["bank_transaction_id"], reason

        if ids.settlement_utr:
            found, reason = _unique_or_none(self.batch_by_utr.get(ids.settlement_utr, []))
            if found:
                return found, ["settlement_utr"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["settlement_utr"], reason
            found, reason = _unique_or_none(self.batch_by_line_utr.get(ids.settlement_utr, []))
            if found:
                return found, ["settlement_utr"], None
            if reason and reason.startswith("ambiguous"):
                return None, ["settlement_utr"], reason

        if ids.bank_transaction_id or ids.settlement_utr:
            return None, [], "bank_transaction_id/settlement_utr did not uniquely match a batch result"

        return None, [], "no unique batch-level identifier match"

    def find_downstream(
        self, anomaly: AnomalyRecord, ids: IdentifierSet, rule
    ) -> Optional[ReconciliationResult]:
        if rule.effect_level != ResultLevel.BATCH:
            return None
        if not ids.settlement_id:
            return None
        candidates = [
            result
            for result in self.batch_by_settlement.get(ids.settlement_id, [])
            if result.primary_status == rule.effect_status
        ]
        found, _reason = _unique_or_none(candidates)
        return found


def compare_run(
    run: ReconciliationRun,
    anomalies: list[AnomalyRecord],
    *,
    seed: Optional[int] = None,
    num_records: Optional[int] = None,
) -> EvaluationReport:
    """Compare a reconciliation run to ground-truth anomalies. Does not read files."""
    index = _ResultIndex(run)
    detected: list[AnomalyEvaluation] = []
    missed: list[AnomalyEvaluation] = []
    incorrect: list[AnomalyEvaluation] = []
    downstream: list[DownstreamEffect] = []

    primary_explained: set[int] = set()
    downstream_explained: set[int] = set()

    ordered = sorted(anomalies, key=lambda a: a.anomaly_id)
    for anomaly in ordered:
        ids = identifiers_from_anomaly(anomaly)
        expected = EXPECTED_PRIMARY_STATUS[anomaly.anomaly_type]
        matched, keys, miss_reason = index.match_primary(anomaly, ids)
        ids.match_keys = keys

        if matched is None:
            missed.append(
                AnomalyEvaluation(
                    anomaly_id=anomaly.anomaly_id,
                    anomaly_type=anomaly.anomaly_type,
                    outcome="MISSED",
                    identifiers=ids,
                    expected_statuses=sorted(s.value for s in expected),
                    miss_reason=miss_reason,
                )
            )
        else:
            primary_explained.add(id(matched))
            evaluation = AnomalyEvaluation(
                anomaly_id=anomaly.anomaly_id,
                anomaly_type=anomaly.anomaly_type,
                outcome="DETECTED",
                identifiers=ids,
                expected_statuses=sorted(s.value for s in expected),
                observed_status=matched.primary_status.value,
                observed_level=matched.level,
                matched_result=result_to_ref(matched),
            )
            if matched.primary_status in expected:
                detected.append(evaluation)
            else:
                evaluation.outcome = "INCORRECT_CLASSIFICATION"
                incorrect.append(evaluation)

        for rule in DOWNSTREAM_RULES:
            if rule.cause != anomaly.anomaly_type:
                continue
            effect = index.find_downstream(anomaly, ids, rule)
            if effect is None:
                continue
            downstream_explained.add(id(effect))
            downstream.append(
                DownstreamEffect(
                    anomaly_id=anomaly.anomaly_id,
                    cause_type=anomaly.anomaly_type,
                    effect_status=rule.effect_status,
                    effect_level=rule.effect_level,
                    reason=rule.reason,
                    result=result_to_ref(effect),
                )
            )

    false_positives: list[FalsePositive] = []
    exception_results = [r for r in run.payment_results + run.batch_results if is_exception(r)]
    exception_results.sort(
        key=lambda r: (
            r.level.value,
            r.evidence.settlement_id or "",
            r.evidence.payment_id or "",
            r.primary_status.value,
        )
    )
    for result in exception_results:
        if id(result) in primary_explained or id(result) in downstream_explained:
            continue
        false_positives.append(FalsePositive(result=result_to_ref(result)))

    type_order = [t.value for t in AnomalyType]
    by_type_map: dict[str, TypeMetrics] = {
        name: TypeMetrics(anomaly_type=name) for name in type_order
    }
    for anomaly in ordered:
        by_type_map[anomaly.anomaly_type.value].ground_truth_count += 1
    for item in detected:
        by_type_map[item.anomaly_type.value].correctly_detected += 1
    for item in missed:
        by_type_map[item.anomaly_type.value].missed += 1
    for item in incorrect:
        by_type_map[item.anomaly_type.value].incorrectly_classified += 1

    total = len(ordered)
    correct_n = len(detected)
    missed_n = len(missed)
    incorrect_n = len(incorrect)
    matched_n = correct_n + incorrect_n
    detection_rate = (matched_n / total) if total else 0.0
    exact_recall = (correct_n / total) if total else 0.0
    classification_accuracy = (correct_n / matched_n) if matched_n else None

    metrics = OverallMetrics(
        total_ground_truth_anomalies=total,
        correctly_detected=correct_n,
        missed_anomalies=missed_n,
        incorrectly_classified=incorrect_n,
        false_positives=len(false_positives),
        detection_rate=detection_rate,
        classification_accuracy=classification_accuracy,
        exact_recall=exact_recall,
        metric_definitions=METRIC_DEFINITIONS,
    )

    return EvaluationReport(
        seed=seed,
        num_records=num_records,
        metrics=metrics,
        by_type=[by_type_map[name] for name in type_order],
        detected=detected,
        missed=missed,
        incorrectly_classified=incorrect,
        false_positive_details=false_positives,
        downstream_effects=downstream,
    )


def evaluate_directory(data_dir: Path) -> EvaluationReport:
    """Load CSVs, run the engine, load ground truth, and compare.

    The engine is invoked only with CSV data. Ground truth is loaded afterwards.
    """
    data = CSVLoader.load_all(data_dir)
    run = ReconciliationEngine(data).reconcile()

    gt_path = data_dir / "ground_truth.json"
    if gt_path.exists():
        anomalies, seed, num_records = load_ground_truth(gt_path)
    else:
        anomalies, seed, num_records = [], None, None

    return compare_run(run, anomalies, seed=seed, num_records=num_records)
