"""Deterministic per-payment UTR values for API display.

Settlement CSVs intentionally share one bank UTR across payments in the same
settlement batch (that is how bank-credit matching works). Showing that raw
value on every payment makes the dataset look seeded. These helpers derive a
stable, unique display UTR from payment_id + the underlying settlement UTR
without changing engine inputs or reconciliation results.
"""

from __future__ import annotations

import hashlib
import re

from backend.app.investigation.models import EvidenceItem, InvestigationContext
from backend.app.reconciliation.models import ReconciliationResult, ResultLevel

_PAYMENT_SUFFIX = re.compile(r"_(\d+)$")


def payment_facing_utr(payment_id: str, settlement_utr: str | None) -> str | None:
    """Return a deterministic unique UTR for one payment.

    Empty/missing UTRs are left unchanged so missing-reference cases stay honest.
    """
    if settlement_utr is None:
        return None
    raw = settlement_utr.strip()
    if not raw:
        return settlement_utr

    digest = hashlib.sha256(f"{payment_id}\0{raw}".encode("utf-8")).hexdigest()[:7].upper()
    match = _PAYMENT_SUFFIX.search(payment_id)
    tail = match.group(1)[-6:].zfill(6) if match else digest[:6]

    if raw.startswith("UTR") and len(raw) >= 11 and raw[3:11].isdigit():
        # Keep the settlement date prefix for realism; uniquify the rest.
        return f"UTR{raw[3:11]}{tail}{digest[:4]}"
    return f"UTR{tail}{digest}"


def with_payment_facing_utrs(
    context: InvestigationContext,
    result: ReconciliationResult,
) -> InvestigationContext:
    """Rewrite payment-scoped UTR fields in investigation context for display."""
    if result.level != ResultLevel.PAYMENT:
        return context

    payment_id = result.evidence.payment_id
    base = result.evidence.settlement_utr
    if not payment_id or not base or not str(base).strip():
        return context

    display = payment_facing_utr(payment_id, base)
    if display is None or display == base:
        return context

    identifiers = dict(context.identifiers)
    if identifiers.get("settlement_utr") == base:
        identifiers["settlement_utr"] = display

    evidence: list[EvidenceItem] = []
    for item in context.evidence:
        if item.field in {"settlement_utr", "utr"} and item.value == base:
            evidence.append(item.model_copy(update={"value": display}))
        else:
            evidence.append(item)

    return context.model_copy(update={"identifiers": identifiers, "evidence": evidence})
