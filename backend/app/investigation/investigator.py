"""AI investigator service.

Investigates deterministic reconciliation exceptions and returns a structured
recommendation. It never mutates the reconciliation run, the source records, or
the deterministic status: it only produces a separate `InvestigationReport`.
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from backend.app.reconciliation.loader import LoadedData
from backend.app.reconciliation.models import ReconciliationResult, ReconciliationRun

from .config import InvestigatorConfig
from .context import (
    ALLOWED_CLASSIFICATIONS,
    ELIGIBLE_STATUSES,
    InvestigationContextBuilder,
    is_eligible,
)
from .models import (
    AIInvestigation,
    GuardrailViolation,
    InvestigationContext,
    InvestigationOutcome,
    InvestigationRecord,
    InvestigationReport,
)
from .provider import LLMProvider, LLMProviderError

SYSTEM_PROMPT = """You are a reconciliation exception investigator for a payments finance team.

The deterministic reconciliation engine is the financial source of truth. You investigate; you do not decide financial outcomes.

You MUST:
- use only the evidence items supplied in the context
- cite evidence by its exact evidence_id in supporting_evidence and contradictory_evidence
- treat every deterministic amount and variance as authoritative
- set human_review_required to true whenever evidence is insufficient, contradictory, or multiple explanations remain plausible
- always set financial_records_modified to false

You MUST NOT:
- invent transactions, identifiers, UTRs, amounts or timestamps
- cite an evidence_id that was not supplied
- match records by amount similarity
- claim an exception is resolved

Respond with a single JSON object and nothing else, using exactly these keys:
exception_id, finding, classification, confidence, supporting_evidence, contradictory_evidence, recommendation, human_review_required, financial_records_modified

confidence is a number between 0 and 1 expressing confidence in your investigation, not financial certainty.
classification must be one of the allowed_classifications supplied in the context.
If the supplied evidence cannot explain the exception, say so in finding, use a low confidence and escalate."""

# Obvious identifier shapes used in this project. Not a general NLP extractor.
_PROSE_IDENTIFIER_RE = re.compile(
    r"\b(?:"
    r"EV\d{3,}"
    r"|pay_[A-Za-z0-9]+"
    r"|order_[A-Za-z0-9]+"
    r"|batch_[A-Za-z0-9]+"
    r"|setl_[A-Za-z0-9]+"
    r"|bank_txn_[A-Za-z0-9]+"
    r"|UTR[A-Za-z0-9]+"
    r"|EXC-[A-Z]+-[A-Za-z0-9_-]+"
    r")\b"
)


def build_user_prompt(context: InvestigationContext) -> str:
    """Serialize the bounded context as the user prompt."""
    return json.dumps(context.model_dump(mode="json"), indent=2, sort_keys=True)


def _extract_json(text: str) -> dict:
    """Parse a JSON object from the raw model response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object at the top level")
    return parsed


def _supplied_identifier_tokens(context: InvestigationContext) -> set[str]:
    """Exact identifier strings the AI is allowed to mention."""
    allowed = set(context.evidence_ids())
    allowed.add(context.exception_id)
    for value in context.identifiers.values():
        allowed.add(value)
        allowed.update(part.strip() for part in value.split(",") if part.strip())
    for item in context.evidence:
        allowed.add(item.record_id)
        allowed.add(item.value)
    return {token for token in allowed if token}


def _ungrounded_prose_identifiers(
    investigation: AIInvestigation, context: InvestigationContext
) -> list[str]:
    """Obvious identifier tokens in finding/recommendation that were not supplied."""
    allowed = _supplied_identifier_tokens(context)
    text = f"{investigation.finding}\n{investigation.recommendation}"
    seen: list[str] = []
    for token in _PROSE_IDENTIFIER_RE.findall(text):
        if token not in allowed and token not in seen:
            seen.append(token)
    return seen


class AIInvestigator:
    """Investigates eligible exceptions using a mockable LLM provider."""

    def __init__(self, provider: LLMProvider, config: Optional[InvestigatorConfig] = None):
        self.provider = provider
        self.config = config or InvestigatorConfig()

    def eligible_results(self, run: ReconciliationRun) -> list[ReconciliationResult]:
        """Deterministic results the AI is allowed to investigate."""
        return [
            result
            for result in list(run.payment_results) + list(run.batch_results)
            if is_eligible(result)
        ]

    def investigate_run(
        self, run: ReconciliationRun, data: Optional[LoadedData] = None
    ) -> InvestigationReport:
        """Investigate every eligible exception in a reconciliation run.

        The run is read-only here; no field of it is written.
        """
        builder = InvestigationContextBuilder(
            data=data, max_evidence_items=self.config.max_evidence_items
        )
        all_results = list(run.payment_results) + list(run.batch_results)
        eligible = [result for result in all_results if is_eligible(result)]

        records = [self.investigate_result(result, builder) for result in eligible]

        return InvestigationReport(
            records=records,
            total_results=len(all_results),
            eligible_exceptions=len(eligible),
            skipped_not_eligible=len(all_results) - len(eligible),
            investigated=sum(
                1 for r in records if r.outcome == InvestigationOutcome.INVESTIGATED
            ),
            escalated=sum(1 for r in records if r.outcome == InvestigationOutcome.ESCALATED),
            failed=sum(1 for r in records if r.outcome == InvestigationOutcome.FAILED),
            human_review_required_count=sum(1 for r in records if r.human_review_required),
            financial_records_modified=False,
        )

    def investigate_result(
        self,
        result: ReconciliationResult,
        builder: Optional[InvestigationContextBuilder] = None,
    ) -> InvestigationRecord:
        """Investigate one deterministic exception, failing safely on any error."""
        if not is_eligible(result):
            raise ValueError(
                f"{result.primary_status.value} is not an AI-eligible exception; "
                f"eligible statuses are {sorted(s.value for s in ELIGIBLE_STATUSES)}"
            )

        builder = builder or InvestigationContextBuilder(
            max_evidence_items=self.config.max_evidence_items
        )
        context = builder.build(result)

        try:
            raw = self.provider.complete(SYSTEM_PROMPT, build_user_prompt(context))
        except LLMProviderError as exc:
            return self._failure(context, result, f"Provider failure: {exc}")
        except Exception as exc:  # a misbehaving provider must not break the run
            return self._failure(context, result, f"Unexpected provider error: {exc}")

        try:
            payload = _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            return self._failure(context, result, f"Response was not valid JSON: {exc}")

        try:
            investigation = AIInvestigation.model_validate(payload)
        except ValidationError as exc:
            return self._failure(
                context, result, f"Response did not match the investigation schema: {exc.error_count()} error(s)"
            )

        return self._apply_guardrails(context, result, investigation)

    def _apply_guardrails(
        self,
        context: InvestigationContext,
        result: ReconciliationResult,
        investigation: AIInvestigation,
    ) -> InvestigationRecord:
        """Flag boundary violations and force escalation where required."""
        violations: list[GuardrailViolation] = []
        supplied_ids = context.evidence_ids()

        invalid_supporting = [ref for ref in investigation.supporting_evidence if ref not in supplied_ids]
        invalid_contradictory = [
            ref for ref in investigation.contradictory_evidence if ref not in supplied_ids
        ]
        invalid_refs = invalid_supporting + invalid_contradictory
        if invalid_refs:
            violations.append(GuardrailViolation.HALLUCINATED_EVIDENCE_REFERENCE)

        if investigation.exception_id != context.exception_id:
            violations.append(GuardrailViolation.EXCEPTION_ID_MISMATCH)

        if investigation.classification not in ALLOWED_CLASSIFICATIONS:
            violations.append(GuardrailViolation.UNSUPPORTED_CLASSIFICATION)

        if investigation.classification != result.primary_status:
            violations.append(GuardrailViolation.CLASSIFICATION_DISAGREES_WITH_ENGINE)

        if investigation.financial_records_modified:
            violations.append(GuardrailViolation.CLAIMED_FINANCIAL_MODIFICATION)

        prose_ungrounded = _ungrounded_prose_identifiers(investigation, context)
        if prose_ungrounded:
            violations.append(GuardrailViolation.UNGROUNDED_IDENTIFIER_IN_PROSE)

        # Sanitize: keep only citations the engine actually supplied, and never
        # let an AI claim of record modification survive into stored output.
        sanitized = investigation.model_copy(
            update={
                "exception_id": context.exception_id,
                "supporting_evidence": [
                    ref for ref in investigation.supporting_evidence if ref in supplied_ids
                ],
                "contradictory_evidence": [
                    ref for ref in investigation.contradictory_evidence if ref in supplied_ids
                ],
                "financial_records_modified": False,
            }
        )

        if not sanitized.supporting_evidence:
            violations.append(GuardrailViolation.NO_SUPPORTING_EVIDENCE)
        if sanitized.contradictory_evidence:
            violations.append(GuardrailViolation.CONTRADICTORY_EVIDENCE)
        if sanitized.confidence < self.config.confidence_threshold:
            violations.append(GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD)

        human_review = bool(violations) or sanitized.human_review_required
        sanitized = sanitized.model_copy(update={"human_review_required": human_review})

        return InvestigationRecord(
            exception_id=context.exception_id,
            deterministic_status=result.primary_status,
            deterministic_rule=result.evidence.rule_applied,
            result_level=result.level,
            outcome=(
                InvestigationOutcome.ESCALATED if human_review else InvestigationOutcome.INVESTIGATED
            ),
            investigation=sanitized,
            human_review_required=human_review,
            guardrail_violations=violations,
            invalid_evidence_references=invalid_refs + [
                token for token in prose_ungrounded if token not in invalid_refs
            ],
            evidence_count=len(context.evidence),
            evidence_dropped_count=context.evidence_dropped_count,
            financial_records_modified=False,
        )

    def _failure(
        self,
        context: InvestigationContext,
        result: ReconciliationResult,
        reason: str,
    ) -> InvestigationRecord:
        """Safe fallback: deterministic result stands, exception goes to a human."""
        return InvestigationRecord(
            exception_id=context.exception_id,
            deterministic_status=result.primary_status,
            deterministic_rule=result.evidence.rule_applied,
            result_level=result.level,
            outcome=InvestigationOutcome.FAILED,
            investigation=None,
            human_review_required=True,
            failure_reason=reason,
            evidence_count=len(context.evidence),
            evidence_dropped_count=context.evidence_dropped_count,
            financial_records_modified=False,
        )
