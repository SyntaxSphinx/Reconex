"""Tests for the Phase 3B AI investigation layer.

No test requires a real LLM or network access; the provider is always mocked.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.app.investigation import (
    AIInvestigator,
    ELIGIBLE_STATUSES,
    EvidenceSource,
    GuardrailViolation,
    InvestigationContextBuilder,
    InvestigationOutcome,
    InvestigatorConfig,
    LLMProviderError,
    OpenAICompatibleProvider,
    exception_id_for,
    is_eligible,
)
from backend.app.models import (
    BankTransaction,
    Payment,
    PaymentStatus,
    SettlementEntityType,
    SettlementRecord,
    TransactionType,
)
from backend.app.reconciliation import (
    ReconciliationEngine,
    ReconciliationStatus,
    ResultLevel,
)
from backend.app.reconciliation.loader import LoadedData
from backend.app.reconciliation.models import (
    ReconciliationEvidence,
    ReconciliationResult,
)


# --------------------------------------------------------------------------
# Mock providers
# --------------------------------------------------------------------------


class ScriptedProvider:
    """Returns a fixed raw response and records the prompts it received."""

    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


class FailingProvider:
    """Simulates a provider outage or timeout."""

    def __init__(self, exc: Exception = None):
        self.exc = exc or LLMProviderError("LLM request timed out")
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        raise self.exc


def json_response(**overrides) -> str:
    payload = {
        "exception_id": "EXC-BATCH-batch_001",
        "finding": "Settlement batch net does not equal the bank credit.",
        "classification": "AMOUNT_MISMATCH",
        "confidence": 0.92,
        "supporting_evidence": ["EV001"],
        "contradictory_evidence": [],
        "recommendation": "Confirm the bank credit with the settlement provider.",
        "human_review_required": False,
        "financial_records_modified": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


def json_response_for(result: ReconciliationResult, **overrides) -> str:
    """A valid mocked response aligned to one engine result."""
    return json_response(
        exception_id=exception_id_for(result),
        classification=result.primary_status.value,
        **overrides,
    )


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def make_batch_amount_mismatch() -> ReconciliationResult:
    """A batch-level AMOUNT_MISMATCH result, as the engine would emit it."""
    return ReconciliationResult(
        primary_status=ReconciliationStatus.AMOUNT_MISMATCH,
        level=ResultLevel.BATCH,
        evidence=ReconciliationEvidence(
            settlement_id="batch_001",
            settlement_utr="UTR001",
            settlement_entity_ids=["setl_001"],
            bank_transaction_id="bank_txn_001",
            settlement_credit_paise=97300,
            settlement_debit_paise=0,
            settlement_amount_paise=97300,
            bank_amount_paise=90000,
            expected_amount_paise=97300,
            actual_amount_paise=90000,
            variance_paise=7300,
            rule_applied="AMOUNT_MISMATCH: Batch net does not match bank credit",
        ),
        message="Settlement batch net differs from bank credit",
    )


def make_reconciled_result() -> ReconciliationResult:
    return ReconciliationResult(
        primary_status=ReconciliationStatus.RECONCILED,
        level=ResultLevel.PAYMENT,
        evidence=ReconciliationEvidence(payment_id="pay_001", settlement_id="batch_001"),
    )


def make_loaded_data() -> LoadedData:
    return LoadedData(
        payments=[
            Payment(
                payment_id="pay_001",
                order_id="order_001",
                customer_id="cust_001",
                amount=100000,
                currency="INR",
                payment_date=datetime(2024, 1, 15, 10, 0, 0),
                status=PaymentStatus.CAPTURED,
                refund_amount=0,
            )
        ],
        settlements=[
            SettlementRecord(
                entity_id="setl_001",
                type=SettlementEntityType.PAYMENT,
                payment_id="pay_001",
                order_id="order_001",
                settlement_id="batch_001",
                settlement_utr="UTR001",
                amount=100000,
                debit=0,
                credit=97300,
                fee=1800,
                tax=324,
                settled_at=datetime(2024, 1, 16, 9, 0, 0),
                description="Payment settlement",
            )
        ],
        bank_transactions=[
            BankTransaction(
                bank_transaction_id="bank_txn_001",
                transaction_date=datetime(2024, 1, 16, 10, 0, 0),
                description="Settlement credit",
                amount=90000,
                transaction_type=TransactionType.CREDIT,
                utr="UTR001",
            )
        ],
    )


@pytest.fixture
def result() -> ReconciliationResult:
    return make_batch_amount_mismatch()


@pytest.fixture
def builder() -> InvestigationContextBuilder:
    return InvestigationContextBuilder(data=make_loaded_data())


# --------------------------------------------------------------------------
# Eligibility and context
# --------------------------------------------------------------------------


class TestEligibility:
    def test_eligible_statuses_match_the_spec(self):
        assert ELIGIBLE_STATUSES == {
            ReconciliationStatus.UNKNOWN,
            ReconciliationStatus.AMOUNT_MISMATCH,
            ReconciliationStatus.MISSING_BANK_CREDIT,
            ReconciliationStatus.UNMATCHED_REFERENCE,
            ReconciliationStatus.REFUND_MISMATCH,
        }

    @pytest.mark.parametrize(
        "status",
        [
            ReconciliationStatus.RECONCILED,
            ReconciliationStatus.PENDING_SETTLEMENT,
            ReconciliationStatus.PENDING_BANK_CREDIT,
            ReconciliationStatus.DUPLICATE,
            ReconciliationStatus.MISSING_SETTLEMENT,
        ],
    )
    def test_deterministic_statuses_are_not_eligible(self, status):
        deterministic = ReconciliationResult(
            primary_status=status,
            level=ResultLevel.PAYMENT,
            evidence=ReconciliationEvidence(payment_id="pay_001"),
        )
        assert is_eligible(deterministic) is False

    def test_investigating_an_ineligible_result_raises(self, builder):
        investigator = AIInvestigator(provider=ScriptedProvider(json_response()))
        with pytest.raises(ValueError):
            investigator.investigate_result(make_reconciled_result(), builder)

    def test_exception_id_is_stable(self, result):
        assert exception_id_for(result) == exception_id_for(make_batch_amount_mismatch())
        assert exception_id_for(result) == "EXC-BATCH-batch_001"


class TestContext:
    def test_evidence_ids_are_unique_and_stable(self, builder, result):
        first = builder.build(result)
        second = builder.build(make_batch_amount_mismatch())
        ids = [item.evidence_id for item in first.evidence]
        assert len(ids) == len(set(ids))
        assert ids == [item.evidence_id for item in second.evidence]

    def test_context_carries_deterministic_amounts(self, builder, result):
        context = builder.build(result)
        values = {(item.field, item.value) for item in context.evidence}
        assert ("variance_paise", "7300") in values
        assert ("expected_amount_paise", "97300") in values

    def test_context_is_bounded_by_max_evidence_items(self, result):
        small = InvestigationContextBuilder(data=make_loaded_data(), max_evidence_items=3)
        assert len(small.build(result).evidence) == 3

    def test_context_only_contains_supplied_records(self, builder, result):
        context = builder.build(result)
        record_ids = {item.record_id for item in context.evidence}
        assert record_ids <= {"EXC-BATCH-batch_001", "pay_001", "setl_001", "bank_txn_001"}

    def test_bank_evidence_survives_cap_when_many_settlement_lines(self):
        data = make_loaded_data()
        for index in range(2, 16):
            data.settlements.append(
                SettlementRecord(
                    entity_id=f"setl_{index:03d}",
                    type=SettlementEntityType.PAYMENT,
                    payment_id=f"pay_{index:03d}",
                    order_id=f"order_{index:03d}",
                    settlement_id="batch_001",
                    settlement_utr="UTR001",
                    amount=100000,
                    debit=0,
                    credit=97300,
                    fee=1800,
                    tax=324,
                    settled_at=datetime(2024, 1, 16, 9, 0, 0),
                    description="Payment settlement",
                )
            )
        builder = InvestigationContextBuilder(data=data, max_evidence_items=20)
        context = builder.build(make_batch_amount_mismatch())
        sources = {item.source for item in context.evidence}

        assert len(context.evidence) == 20
        assert EvidenceSource.DETERMINISTIC in sources
        assert EvidenceSource.BANK in sources
        assert any(item.record_id == "bank_txn_001" for item in context.evidence)
        assert context.evidence_dropped_count > 0

    def test_dropped_evidence_count_is_zero_when_everything_fits(self, builder, result):
        context = builder.build(result)
        assert context.evidence_dropped_count == 0


# --------------------------------------------------------------------------
# Investigation outcomes
# --------------------------------------------------------------------------


class TestValidResponse:
    def test_valid_response_is_accepted(self, builder, result):
        provider = ScriptedProvider(json_response())
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.INVESTIGATED
        assert record.guardrail_violations == []
        assert record.human_review_required is False
        assert record.investigation is not None
        assert record.investigation.classification == ReconciliationStatus.AMOUNT_MISMATCH
        assert record.investigation.supporting_evidence == ["EV001"]
        assert record.investigation.financial_records_modified is False
        assert record.deterministic_status == ReconciliationStatus.AMOUNT_MISMATCH

    def test_provider_receives_only_the_bounded_context(self, builder, result):
        provider = ScriptedProvider(json_response())
        AIInvestigator(provider=provider).investigate_result(result, builder)

        _, user_prompt = provider.calls[0]
        payload = json.loads(user_prompt)
        assert set(payload) == {
            "exception_id",
            "deterministic_status",
            "result_level",
            "rule_applied",
            "message",
            "identifiers",
            "evidence",
            "allowed_classifications",
            "evidence_dropped_count",
        }

    def test_response_in_a_code_fence_is_parsed(self, builder, result):
        provider = ScriptedProvider(f"```json\n{json_response()}\n```")
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        assert record.outcome == InvestigationOutcome.INVESTIGATED


class TestInvalidResponse:
    def test_malformed_json_fails_safely(self, builder, result):
        provider = ScriptedProvider("I think the batch is short by some amount.")
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED
        assert record.investigation is None
        assert record.human_review_required is True
        assert "not valid JSON" in record.failure_reason

    def test_response_missing_required_fields_fails_schema_validation(self, builder, result):
        provider = ScriptedProvider(json.dumps({"exception_id": "EXC-BATCH-batch_001"}))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED
        assert record.investigation is None
        assert "schema" in record.failure_reason

    def test_unsupported_classification_fails_schema_validation(self, builder, result):
        provider = ScriptedProvider(json_response(classification="FRAUD_SUSPECTED"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED
        assert record.human_review_required is True

    def test_deterministic_only_classification_is_rejected(self, builder, result):
        provider = ScriptedProvider(json_response(classification="RECONCILED"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.human_review_required is True
        assert GuardrailViolation.UNSUPPORTED_CLASSIFICATION in record.guardrail_violations

    def test_extra_fields_are_rejected(self, builder, result):
        provider = ScriptedProvider(json_response(corrected_bank_amount_paise=97300))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED

    def test_out_of_range_confidence_is_rejected(self, builder, result):
        provider = ScriptedProvider(json_response(confidence=1.4))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED


class TestHallucinatedEvidence:
    def test_hallucinated_supporting_reference_is_flagged_and_escalated(self, builder, result):
        provider = ScriptedProvider(json_response(supporting_evidence=["EV001", "EV999"]))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.ESCALATED
        assert GuardrailViolation.HALLUCINATED_EVIDENCE_REFERENCE in record.guardrail_violations
        assert record.invalid_evidence_references == ["EV999"]
        assert record.investigation.supporting_evidence == ["EV001"]
        assert record.human_review_required is True

    def test_finding_with_no_evidence_citation_is_escalated(self, builder, result):
        provider = ScriptedProvider(json_response(supporting_evidence=[]))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.ESCALATED
        assert GuardrailViolation.NO_SUPPORTING_EVIDENCE in record.guardrail_violations

    def test_mismatched_exception_id_is_flagged(self, builder, result):
        provider = ScriptedProvider(json_response(exception_id="EXC-BATCH-batch_999"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert GuardrailViolation.EXCEPTION_ID_MISMATCH in record.guardrail_violations
        assert record.investigation.exception_id == "EXC-BATCH-batch_001"


class TestHumanReview:
    def test_low_confidence_escalates(self, builder, result):
        provider = ScriptedProvider(json_response(confidence=0.31))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.ESCALATED
        assert GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD in record.guardrail_violations
        assert record.investigation.human_review_required is True

    def test_contradictory_evidence_escalates(self, builder, result):
        provider = ScriptedProvider(
            json_response(supporting_evidence=["EV001"], contradictory_evidence=["EV002"])
        )
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.ESCALATED
        assert GuardrailViolation.CONTRADICTORY_EVIDENCE in record.guardrail_violations

    def test_ai_requested_human_review_is_honoured(self, builder, result):
        provider = ScriptedProvider(json_response(human_review_required=True))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.ESCALATED
        assert record.human_review_required is True

    def test_confidence_threshold_is_configurable(self, builder, result):
        config = InvestigatorConfig(confidence_threshold=0.95)
        provider = ScriptedProvider(json_response(confidence=0.92))
        record = AIInvestigator(provider=provider, config=config).investigate_result(result, builder)

        assert GuardrailViolation.CONFIDENCE_BELOW_THRESHOLD in record.guardrail_violations

    def test_claimed_financial_modification_is_flagged_and_neutralized(self, builder, result):
        provider = ScriptedProvider(json_response(financial_records_modified=True))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert GuardrailViolation.CLAIMED_FINANCIAL_MODIFICATION in record.guardrail_violations
        assert record.financial_records_modified is False
        assert record.investigation.financial_records_modified is False
        assert record.human_review_required is True


class TestProviderFailure:
    def test_provider_error_falls_back_safely(self, builder, result):
        record = AIInvestigator(provider=FailingProvider()).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED
        assert record.investigation is None
        assert record.human_review_required is True
        assert record.deterministic_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert record.financial_records_modified is False

    def test_unexpected_provider_exception_is_contained(self, builder, result):
        provider = FailingProvider(RuntimeError("socket exploded"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.outcome == InvestigationOutcome.FAILED
        assert "Unexpected provider error" in record.failure_reason


# --------------------------------------------------------------------------
# Boundary with the deterministic engine
# --------------------------------------------------------------------------


def build_run_with_exceptions():
    """Run the real engine on a small dataset containing genuine exceptions."""
    data = make_loaded_data()
    data.payments.append(
        Payment(
            payment_id="pay_002",
            order_id="order_002",
            customer_id="cust_002",
            amount=50000,
            currency="INR",
            payment_date=datetime(2024, 1, 15, 11, 0, 0),
            status=PaymentStatus.CAPTURED,
            refund_amount=0,
        )
    )
    return ReconciliationEngine(data).reconcile(), data


class TestEngineBoundary:
    def test_reconciliation_output_is_unchanged_by_investigation(self):
        run, data = build_run_with_exceptions()
        before = run.model_dump(mode="json")

        report = AIInvestigator(provider=ScriptedProvider(json_response())).investigate_run(run, data)

        assert run.model_dump(mode="json") == before
        assert report.financial_records_modified is False

    def test_source_records_are_unchanged_by_investigation(self):
        run, data = build_run_with_exceptions()
        before = data.model_dump(mode="json")

        AIInvestigator(provider=ScriptedProvider(json_response())).investigate_run(run, data)

        assert data.model_dump(mode="json") == before

    def test_clean_records_are_never_sent_to_the_provider(self):
        run, data = build_run_with_exceptions()
        provider = ScriptedProvider(json_response())

        report = AIInvestigator(provider=provider).investigate_run(run, data)

        assert len(provider.calls) == report.eligible_exceptions
        investigated_ids = {record.exception_id for record in report.records}
        for result in list(run.payment_results) + list(run.batch_results):
            if not is_eligible(result):
                assert exception_id_for(result) not in investigated_ids

    def test_investigated_statuses_are_all_eligible(self):
        run, data = build_run_with_exceptions()
        report = AIInvestigator(provider=ScriptedProvider(json_response())).investigate_run(run, data)

        assert report.eligible_exceptions > 0
        for record in report.records:
            assert record.deterministic_status in ELIGIBLE_STATUSES

    def test_deterministic_status_survives_a_conflicting_ai_classification(self, builder, result):
        provider = ScriptedProvider(json_response(classification="UNMATCHED_REFERENCE"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.deterministic_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert record.investigation.classification == ReconciliationStatus.UNMATCHED_REFERENCE
        assert GuardrailViolation.CLASSIFICATION_DISAGREES_WITH_ENGINE in record.guardrail_violations
        assert record.human_review_required is True
        assert record.outcome == InvestigationOutcome.ESCALATED

    def test_report_is_json_serializable(self):
        run, data = build_run_with_exceptions()
        report = AIInvestigator(provider=ScriptedProvider(json_response())).investigate_run(run, data)
        assert json.loads(json.dumps(report.model_dump(mode="json")))


class TestGroundTruthIndependence:
    def test_ai_layer_never_references_ground_truth(self):
        package = Path(__file__).resolve().parent.parent / "backend" / "app" / "investigation"
        for module in package.glob("*.py"):
            source = module.read_text(encoding="utf-8")
            assert "ground_truth" not in source, f"{module.name} references ground truth"
            assert "AnomalyType" not in source, f"{module.name} imports ground-truth anomaly types"

    def test_context_contains_no_ground_truth_keys(self, builder, result):
        serialized = json.dumps(builder.build(result).model_dump(mode="json"))
        assert "anomaly" not in serialized.lower()
        assert "ground_truth" not in serialized.lower()


class TestConfig:
    def test_config_reads_from_environment(self):
        config = InvestigatorConfig.from_env(
            {
                "RECONEX_LLM_MODEL": "some-model",
                "RECONEX_AI_CONFIDENCE_THRESHOLD": "0.8",
            }
        )
        assert config.model == "some-model"
        assert config.confidence_threshold == 0.8

    def test_api_key_is_read_from_env_not_stored(self):
        config = InvestigatorConfig()
        assert "api_key" not in config.model_dump()
        assert config.api_key({"RECONEX_LLM_API_KEY": "secret"}) == "secret"
        assert config.api_key({}) is None


class TestClassificationDisagreement:
    def test_conflicting_eligible_classification_escalates(self, builder, result):
        provider = ScriptedProvider(json_response(classification="UNMATCHED_REFERENCE"))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert record.deterministic_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert record.investigation.classification == ReconciliationStatus.UNMATCHED_REFERENCE
        assert GuardrailViolation.CLASSIFICATION_DISAGREES_WITH_ENGINE in record.guardrail_violations
        assert record.human_review_required is True
        assert record.outcome == InvestigationOutcome.ESCALATED
        assert record.financial_records_modified is False


class TestProseGrounding:
    def test_invented_evidence_id_in_finding_is_flagged(self, builder, result):
        provider = ScriptedProvider(
            json_response(finding="EV999 shows a second bank credit that was omitted.")
        )
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert GuardrailViolation.UNGROUNDED_IDENTIFIER_IN_PROSE in record.guardrail_violations
        assert "EV999" in record.invalid_evidence_references
        assert record.human_review_required is True
        assert record.outcome == InvestigationOutcome.ESCALATED

    def test_invented_utr_in_recommendation_is_flagged(self, builder, result):
        provider = ScriptedProvider(
            json_response(recommendation="Remap the batch to UTR999999 before closing.")
        )
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert GuardrailViolation.UNGROUNDED_IDENTIFIER_IN_PROSE in record.guardrail_violations
        assert "UTR999999" in record.invalid_evidence_references
        assert record.human_review_required is True

    def test_supplied_evidence_id_in_finding_is_allowed(self, builder, result):
        provider = ScriptedProvider(
            json_response(finding="EV001 is the authoritative deterministic status.")
        )
        record = AIInvestigator(provider=provider).investigate_result(result, builder)

        assert GuardrailViolation.UNGROUNDED_IDENTIFIER_IN_PROSE not in record.guardrail_violations
        assert record.outcome == InvestigationOutcome.INVESTIGATED


def _prompt_context(provider: ScriptedProvider) -> dict:
    return json.loads(provider.calls[0][1])


class TestEligibleStatusContext:
    def test_unknown_context_carries_conflict_identifiers(self, builder):
        result = ReconciliationResult(
            primary_status=ReconciliationStatus.UNKNOWN,
            level=ResultLevel.BATCH,
            evidence=ReconciliationEvidence(
                settlement_id="batch_001",
                settlement_entity_ids=["setl_001"],
                conflict_reason="Multiple UTRs in batch: ['UTR001', 'UTR002']",
                rule_applied="UNKNOWN: Conflicting UTRs in settlement batch",
            ),
            message="Settlement batch has conflicting UTRs",
        )
        provider = ScriptedProvider(json_response_for(result))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        payload = _prompt_context(provider)

        assert record.deterministic_status == ReconciliationStatus.UNKNOWN
        assert payload["deterministic_status"] == "UNKNOWN"
        assert payload["identifiers"]["settlement_id"] == "batch_001"
        fields = {item["field"] for item in payload["evidence"]}
        assert "conflict_reason" in fields
        sources = {item["source"] for item in payload["evidence"]}
        assert EvidenceSource.DETERMINISTIC.value in sources
        assert EvidenceSource.SETTLEMENT.value in sources

    def test_amount_mismatch_context_carries_bank_and_variance(self, builder, result):
        provider = ScriptedProvider(json_response_for(result))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        payload = _prompt_context(provider)

        assert record.deterministic_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert payload["identifiers"]["bank_transaction_id"] == "bank_txn_001"
        assert payload["identifiers"]["settlement_utr"] == "UTR001"
        values = {(item["field"], item["value"]) for item in payload["evidence"]}
        assert ("variance_paise", "7300") in values
        sources = {item["source"] for item in payload["evidence"]}
        assert EvidenceSource.BANK.value in sources
        assert EvidenceSource.SETTLEMENT.value in sources

    def test_missing_bank_credit_context_has_settlement_not_a_bank_row(self):
        data = LoadedData(
            payments=make_loaded_data().payments,
            settlements=make_loaded_data().settlements,
            bank_transactions=[],
        )
        result = ReconciliationResult(
            primary_status=ReconciliationStatus.MISSING_BANK_CREDIT,
            level=ResultLevel.BATCH,
            evidence=ReconciliationEvidence(
                settlement_id="batch_001",
                settlement_utr="UTR_MISSING",
                settlement_entity_ids=["setl_001"],
                expected_amount_paise=97300,
                rule_applied="MISSING_BANK_CREDIT: Beyond bank credit window",
            ),
            message="No bank credit found for settlement UTR",
        )
        builder = InvestigationContextBuilder(data=data)
        provider = ScriptedProvider(json_response_for(result))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        payload = _prompt_context(provider)

        assert record.deterministic_status == ReconciliationStatus.MISSING_BANK_CREDIT
        assert payload["identifiers"]["settlement_id"] == "batch_001"
        assert payload["identifiers"]["settlement_utr"] == "UTR_MISSING"
        assert "bank_transaction_id" not in payload["identifiers"]
        sources = {item["source"] for item in payload["evidence"]}
        assert EvidenceSource.BANK.value not in sources
        assert EvidenceSource.SETTLEMENT.value in sources
        fields = {item["field"] for item in payload["evidence"]}
        assert "expected_amount_paise" in fields

    def test_unmatched_reference_context_carries_payment_and_utr(self, builder):
        result = ReconciliationResult(
            primary_status=ReconciliationStatus.UNMATCHED_REFERENCE,
            level=ResultLevel.PAYMENT,
            evidence=ReconciliationEvidence(
                payment_id="pay_001",
                order_id="order_001",
                settlement_id="batch_001",
                settlement_utr="UTR_CORRUPT",
                settlement_entity_ids=["setl_001"],
                rule_applied="UNMATCHED_REFERENCE: Settlement line has no valid UTR",
            ),
            message="Settlement line UTR does not match batch majority",
        )
        provider = ScriptedProvider(json_response_for(result))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        payload = _prompt_context(provider)

        assert record.deterministic_status == ReconciliationStatus.UNMATCHED_REFERENCE
        assert payload["identifiers"]["payment_id"] == "pay_001"
        assert payload["identifiers"]["settlement_utr"] == "UTR_CORRUPT"
        sources = {item["source"] for item in payload["evidence"]}
        assert EvidenceSource.PAYMENT.value in sources
        assert EvidenceSource.SETTLEMENT.value in sources
        record_ids = {item["record_id"] for item in payload["evidence"]}
        assert "pay_001" in record_ids
        assert "setl_001" in record_ids

    def test_refund_mismatch_context_carries_refund_amounts(self):
        data = make_loaded_data()
        data.payments[0].refund_amount = 5000
        result = ReconciliationResult(
            primary_status=ReconciliationStatus.REFUND_MISMATCH,
            level=ResultLevel.PAYMENT,
            evidence=ReconciliationEvidence(
                payment_id="pay_001",
                order_id="order_001",
                settlement_id="batch_001",
                settlement_entity_ids=["setl_001"],
                payment_refund_amount_paise=5000,
                settlement_refund_amount_paise=0,
                rule_applied="REFUND_MISMATCH: Payment refund does not match settlement refund",
            ),
            message="Refund amounts differ",
        )
        builder = InvestigationContextBuilder(data=data)
        provider = ScriptedProvider(json_response_for(result))
        record = AIInvestigator(provider=provider).investigate_result(result, builder)
        payload = _prompt_context(provider)

        assert record.deterministic_status == ReconciliationStatus.REFUND_MISMATCH
        assert payload["identifiers"]["payment_id"] == "pay_001"
        values = {(item["field"], item["value"]) for item in payload["evidence"]}
        assert ("payment_refund_amount_paise", "5000") in values
        assert ("settlement_refund_amount_paise", "0") in values
        assert ("refund_amount", "5000") in values
        sources = {item["source"] for item in payload["evidence"]}
        assert EvidenceSource.PAYMENT.value in sources
        assert EvidenceSource.SETTLEMENT.value in sources


class TestProviderStructuredOutput:
    def test_openai_endpoint_sends_investigation_json_schema(self):
        provider = OpenAICompatibleProvider(InvestigatorConfig())
        fmt = provider.response_format()

        assert fmt["type"] == "json_schema"
        assert fmt["json_schema"]["name"] == "ai_investigation"
        assert fmt["json_schema"]["strict"] is True
        schema = fmt["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert "finding" in schema["required"]
        assert "classification" in schema["properties"]

    def test_generic_endpoint_keeps_json_object_fallback(self):
        provider = OpenAICompatibleProvider(
            InvestigatorConfig(base_url="https://example.invalid/v1")
        )
        assert provider.response_format() == {"type": "json_object"}
