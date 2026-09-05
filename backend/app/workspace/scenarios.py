"""Deterministic input transforms applied before ReconciliationEngine.reconcile()."""

from __future__ import annotations

from collections import defaultdict

from backend.app.models import PaymentStatus, SettlementEntityType
from backend.app.reconciliation.loader import LoadedData

SCENARIO_NORMAL = "normal"
SCENARIO_REFUND_SPIKE = "refund_spike"
SCENARIO_SETTLEMENT_DELAY = "settlement_delay"
SCENARIO_DUPLICATE = "duplicate_payment"
SCENARIO_BANK_FILE = "bank_file_issue"

SCENARIO_LABELS: dict[str, str] = {
    SCENARIO_NORMAL: "Normal Day",
    SCENARIO_REFUND_SPIKE: "Refund Spike",
    SCENARIO_SETTLEMENT_DELAY: "Settlement Delay",
    SCENARIO_DUPLICATE: "Duplicate Payment Incident",
    SCENARIO_BANK_FILE: "Bank File Issue",
}

# Extra exceptions layered on top of the existing ~20 payment exceptions
# in the generated 1,000-payment dataset.
_REFUND_SPIKE_EXTRA = 18
_SETTLEMENT_DELAY_EXTRA = 38
_DUPLICATE_EXTRA = 28
_BANK_UNMATCHED_EXTRA = 35


class UnknownScenarioError(ValueError):
    """Raised when POST /api/runs receives an unsupported scenario."""


def parse_scenario(value: str | None) -> str:
    key = (value or SCENARIO_NORMAL).strip().lower()
    if key not in SCENARIO_LABELS:
        allowed = ", ".join(sorted(SCENARIO_LABELS))
        raise UnknownScenarioError(
            f"Unsupported scenario '{value}'. Expected one of: {allowed}"
        )
    return key


def apply_scenario(data: LoadedData, scenario: str) -> LoadedData:
    """Return a deep copy of CSV data, optionally perturbed for a scenario.

    The original LoadedData is never mutated. The engine still performs
    reconciliation on the returned copy.
    """
    key = parse_scenario(scenario)
    clone = data.model_copy(deep=True)
    if key == SCENARIO_NORMAL:
        return clone
    if key == SCENARIO_REFUND_SPIKE:
        return _refund_spike(clone)
    if key == SCENARIO_SETTLEMENT_DELAY:
        return _settlement_delay(clone)
    if key == SCENARIO_DUPLICATE:
        return _duplicate_payment(clone)
    return _bank_file_issue(clone)


def _payment_lines(data: LoadedData) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for line in data.settlements:
        if line.payment_id and line.type == SettlementEntityType.PAYMENT:
            grouped[line.payment_id].append(line)
    return grouped


def _candidate_payment_ids(data: LoadedData) -> list[str]:
    """Payments that look cleanly settled — safe to turn into extra exceptions."""
    lines = _payment_lines(data)
    chosen: list[str] = []
    for payment in sorted(data.payments, key=lambda item: item.payment_id):
        if payment.status != PaymentStatus.CAPTURED:
            continue
        payment_lines = lines.get(payment.payment_id, [])
        if len(payment_lines) != 1:
            continue
        if payment.refund_amount != 0:
            continue
        line = payment_lines[0]
        if line.amount != payment.amount:
            continue
        if not (line.settlement_utr or "").strip():
            continue
        chosen.append(payment.payment_id)
    return chosen


def _take(ids: list[str], count: int) -> list[str]:
    return ids[: min(count, len(ids))]


def _refund_spike(data: LoadedData) -> LoadedData:
    targets = set(_take(_candidate_payment_ids(data), _REFUND_SPIKE_EXTRA))
    for payment in data.payments:
        if payment.payment_id not in targets:
            continue
        payment.refund_amount = max(100, payment.amount // 20)
    return data


def _settlement_delay(data: LoadedData) -> LoadedData:
    targets = set(_take(_candidate_payment_ids(data), _SETTLEMENT_DELAY_EXTRA))
    data.settlements = [
        line for line in data.settlements if line.payment_id not in targets
    ]
    return data


def _duplicate_payment(data: LoadedData) -> LoadedData:
    targets = set(_take(_candidate_payment_ids(data), _DUPLICATE_EXTRA))
    extras = []
    for line in data.settlements:
        if (
            line.payment_id in targets
            and line.type == SettlementEntityType.PAYMENT
        ):
            extras.append(
                line.model_copy(
                    update={"entity_id": f"{line.entity_id}_DUP"}
                )
            )
    data.settlements = list(data.settlements) + extras
    return data


def _bank_file_issue(data: LoadedData) -> LoadedData:
    targets = set(_take(_candidate_payment_ids(data), _BANK_UNMATCHED_EXTRA))
    for line in data.settlements:
        if (
            line.payment_id in targets
            and line.type == SettlementEntityType.PAYMENT
        ):
            line.settlement_utr = ""
    return data
