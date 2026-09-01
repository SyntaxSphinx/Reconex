"""Tests for Phase 2C independent evaluation harness."""

import inspect
import json
from datetime import datetime, timedelta
from pathlib import Path

from backend.app.evaluation import compare_run, evaluate_directory
from backend.app.evaluation.evaluator import load_ground_truth
from backend.app.generator import AnomalyInjector, CleanDataGenerator, GeneratorConfig
from backend.app.models import (
    BankTransaction,
    Payment,
    PaymentStatus,
    SettlementEntityType,
    SettlementRecord,
    TransactionType,
)
from backend.app.models.anomaly import AnomalyRecord, AnomalyType
from backend.app.reconciliation import (
    LoadedData,
    ReconciliationEngine,
    ReconciliationEvidence,
    ReconciliationResult,
    ReconciliationRun,
    ReconciliationStatus,
    ReconciliationSummary,
    ResultLevel,
)
from backend.app.reconciliation.engine import ReconciliationEngine as EngineClass


def make_payment(**overrides) -> Payment:
    values = {
        "payment_id": "pay_001",
        "order_id": "order_001",
        "customer_id": "cust_001",
        "amount": 100000,
        "currency": "INR",
        "payment_date": datetime(2024, 1, 15, 10, 0, 0),
        "status": PaymentStatus.CAPTURED,
        "refund_amount": 0,
    }
    values.update(overrides)
    return Payment(**values)


def make_settlement(**overrides) -> SettlementRecord:
    values = {
        "entity_id": "setl_001",
        "type": SettlementEntityType.PAYMENT,
        "payment_id": "pay_001",
        "order_id": "order_001",
        "settlement_id": "batch_001",
        "settlement_utr": "UTR001",
        "amount": 100000,
        "debit": 0,
        "credit": 97300,
        "fee": 1800,
        "tax": 900,
        "settled_at": datetime(2024, 1, 16, 9, 0, 0),
        "description": "settlement",
    }
    values.update(overrides)
    return SettlementRecord(**values)


def make_bank(**overrides) -> BankTransaction:
    values = {
        "bank_transaction_id": "bank_001",
        "transaction_date": datetime(2024, 1, 16, 10, 0, 0),
        "description": "credit",
        "amount": 97300,
        "transaction_type": TransactionType.CREDIT,
        "utr": "UTR001",
    }
    values.update(overrides)
    return BankTransaction(**values)


def run_engine(payments, settlements, banks) -> ReconciliationRun:
    return ReconciliationEngine(
        LoadedData(payments=payments, settlements=settlements, bank_transactions=banks)
    ).reconcile()


def gt_record(**overrides) -> AnomalyRecord:
    values = {
        "anomaly_id": "anom_000001",
        "anomaly_type": AnomalyType.MISSING_SETTLEMENT,
        "affected_entity_id": "pay_001",
        "affected_entity_type": "payment",
        "expected_state": "settlement should exist",
        "actual_state": "settlement missing",
        "related_ids": {"payment_id": "pay_001", "order_id": "order_001", "settlement_id": "batch_001"},
        "description": "missing settlement",
    }
    values.update(overrides)
    return AnomalyRecord(**values)


def payment_result(
    status: ReconciliationStatus,
    payment_id: str = "pay_001",
    settlement_id: str | None = "batch_001",
    entity_ids: list[str] | None = None,
) -> ReconciliationResult:
    return ReconciliationResult(
        primary_status=status,
        level=ResultLevel.PAYMENT,
        evidence=ReconciliationEvidence(
            payment_id=payment_id,
            order_id="order_001",
            settlement_id=settlement_id,
            settlement_entity_ids=entity_ids or [],
        ),
    )


def batch_result(
    status: ReconciliationStatus,
    settlement_id: str = "batch_001",
    utr: str | None = "UTR001",
    bank_id: str | None = "bank_001",
) -> ReconciliationResult:
    return ReconciliationResult(
        primary_status=status,
        level=ResultLevel.BATCH,
        evidence=ReconciliationEvidence(
            settlement_id=settlement_id,
            settlement_utr=utr,
            bank_transaction_id=bank_id,
        ),
    )


def fake_run(payments=None, batches=None) -> ReconciliationRun:
    return ReconciliationRun(
        payment_results=payments or [],
        batch_results=batches or [],
        summary=ReconciliationSummary(),
    )


class TestPerfectBaseline:
    def test_clean_dataset_has_no_anomalies_or_false_positives(self):
        generator = CleanDataGenerator(GeneratorConfig(num_records=80, seed=7))
        payments, settlements, banks = generator.generate_clean_data()
        run = run_engine(payments, settlements, banks)
        report = compare_run(run, [])

        assert report.metrics.total_ground_truth_anomalies == 0
        assert report.metrics.correctly_detected == 0
        assert report.metrics.missed_anomalies == 0
        assert report.metrics.false_positives == 0
        assert report.metrics.detection_rate == 0.0
        assert report.metrics.classification_accuracy is None
        assert all(r.primary_status == ReconciliationStatus.RECONCILED for r in run.payment_results)
        assert all(r.primary_status == ReconciliationStatus.RECONCILED for r in run.batch_results)


class TestCorrectDetection:
    def test_missing_settlement_is_detected(self):
        payment = make_payment(payment_date=datetime.utcnow() - timedelta(days=10))
        run = run_engine([payment], [], [])
        report = compare_run(run, [gt_record()])

        assert report.metrics.correctly_detected == 1
        assert report.metrics.missed_anomalies == 0
        assert report.detected[0].observed_status == ReconciliationStatus.MISSING_SETTLEMENT.value
        assert report.detected[0].identifiers.match_keys == ["payment_id"]

    def test_duplicate_is_detected_by_payment_id(self):
        payment = make_payment()
        s1 = make_settlement(entity_id="setl_001")
        s2 = make_settlement(entity_id="setl_001_DUP")
        bank = make_bank(amount=194600)
        run = run_engine([payment], [s1, s2], [bank])
        report = compare_run(
            run,
            [
                gt_record(
                    anomaly_type=AnomalyType.DUPLICATE,
                    affected_entity_id="setl_001",
                    affected_entity_type="settlement",
                    related_ids={
                        "original_entity_id": "setl_001",
                        "duplicate_entity_id": "setl_001_DUP",
                        "payment_id": "pay_001",
                        "settlement_id": "batch_001",
                    },
                )
            ],
        )
        assert report.metrics.correctly_detected == 1
        assert report.detected[0].observed_status == ReconciliationStatus.DUPLICATE.value


class TestMissedAnomaly:
    def test_unmatched_identifiers_are_missed(self):
        run = fake_run(
            payments=[payment_result(ReconciliationStatus.RECONCILED, payment_id="pay_other")],
            batches=[batch_result(ReconciliationStatus.RECONCILED)],
        )
        report = compare_run(run, [gt_record()])
        assert report.metrics.missed_anomalies == 1
        assert report.metrics.correctly_detected == 0
        assert report.missed[0].miss_reason


class TestIncorrectClassification:
    def test_wrong_status_is_incorrect_classification(self):
        run = fake_run(
            payments=[payment_result(ReconciliationStatus.RECONCILED)],
            batches=[batch_result(ReconciliationStatus.RECONCILED)],
        )
        report = compare_run(run, [gt_record()])
        assert report.metrics.incorrectly_classified == 1
        assert report.metrics.correctly_detected == 0
        assert report.incorrectly_classified[0].observed_status == "RECONCILED"
        assert "MISSING_SETTLEMENT" in report.incorrectly_classified[0].expected_statuses


class TestFalsePositive:
    def test_unexplained_duplicate_is_false_positive(self):
        run = fake_run(
            payments=[payment_result(ReconciliationStatus.DUPLICATE, entity_ids=["setl_001", "setl_001_DUP"])],
            batches=[batch_result(ReconciliationStatus.RECONCILED)],
        )
        report = compare_run(run, [])
        assert report.metrics.false_positives == 1
        assert report.false_positive_details[0].result.primary_status == ReconciliationStatus.DUPLICATE


class TestDownstreamConsequence:
    def test_missing_settlement_batch_amount_mismatch_is_not_false_positive(self):
        payment1 = make_payment(payment_id="pay_001", order_id="order_001", amount=100000)
        payment2 = make_payment(payment_id="pay_002", order_id="order_002", amount=200000)
        remaining = make_settlement(
            entity_id="setl_002",
            payment_id="pay_002",
            order_id="order_002",
            amount=200000,
            credit=194600,
        )
        bank = make_bank(amount=97300 + 194600)
        run = run_engine([payment1, payment2], [remaining], [bank])

        report = compare_run(
            run,
            [
                gt_record(
                    related_ids={
                        "payment_id": "pay_001",
                        "order_id": "order_001",
                        "settlement_id": "batch_001",
                        "removed_entity_id": "setl_001",
                    }
                )
            ],
        )

        assert report.metrics.correctly_detected == 1
        assert report.metrics.false_positives == 0
        assert len(report.downstream_effects) == 1
        effect = report.downstream_effects[0]
        assert effect.cause_type == AnomalyType.MISSING_SETTLEMENT
        assert effect.effect_status == ReconciliationStatus.AMOUNT_MISMATCH
        assert effect.effect_level == ResultLevel.BATCH

    def test_unmatched_reference_explains_batch_unknown(self):
        pay1 = make_payment(payment_id="pay_001", order_id="order_001")
        pay2 = make_payment(payment_id="pay_002", order_id="order_002")
        pay3 = make_payment(payment_id="pay_003", order_id="order_003")
        s1 = make_settlement(entity_id="setl_001", payment_id="pay_001", order_id="order_001", settlement_utr="UTR001")
        s2 = make_settlement(entity_id="setl_002", payment_id="pay_002", order_id="order_002", settlement_utr="UTR001")
        s3 = make_settlement(entity_id="setl_003", payment_id="pay_003", order_id="order_003", settlement_utr="UTR_BAD")
        run = run_engine([pay1, pay2, pay3], [s1, s2, s3], [])

        report = compare_run(
            run,
            [
                gt_record(
                    anomaly_id="anom_000031",
                    anomaly_type=AnomalyType.UNMATCHED_REFERENCE,
                    affected_entity_id="setl_003",
                    affected_entity_type="settlement",
                    related_ids={
                        "entity_id": "setl_003",
                        "payment_id": "pay_003",
                        "order_id": "order_003",
                        "settlement_id": "batch_001",
                        "original_utr": "UTR001",
                        "corrupted_utr": "UTR_BAD",
                    },
                )
            ],
        )
        assert report.metrics.correctly_detected == 1
        assert report.metrics.false_positives == 0
        assert any(
            d.effect_status == ReconciliationStatus.UNKNOWN for d in report.downstream_effects
        )


class TestDeterministicEvaluation:
    def test_same_inputs_produce_identical_reports(self):
        generator = CleanDataGenerator(GeneratorConfig(num_records=60, seed=11))
        payments, settlements, banks = generator.generate_clean_data()
        injector = AnomalyInjector(GeneratorConfig(num_records=60, seed=11))
        gt = injector.inject_all_anomalies(payments, settlements, banks)
        run = run_engine(payments, settlements, banks)

        first = compare_run(run, gt, seed=11, num_records=60)
        second = compare_run(run, gt, seed=11, num_records=60)
        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_independent_generation_is_byte_stable(self):
        def _once():
            generator = CleanDataGenerator(GeneratorConfig(num_records=40, seed=21))
            payments, settlements, banks = generator.generate_clean_data()
            injector = AnomalyInjector(GeneratorConfig(num_records=40, seed=21))
            gt = injector.inject_all_anomalies(payments, settlements, banks)
            run = run_engine(payments, settlements, banks)
            return compare_run(run, gt, seed=21, num_records=40).model_dump(mode="json")

        assert _once() == _once()


class TestGroundTruthIndependence:
    def test_engine_source_does_not_mention_ground_truth(self):
        import backend.app.reconciliation.engine as engine_module
        import backend.app.reconciliation.loader as loader_module

        assert "ground_truth" not in inspect.getsource(engine_module)
        assert "ground_truth" not in inspect.getsource(loader_module)
        assert "ground_truth" not in inspect.getsource(EngineClass)


class TestEvaluateDirectory:
    def test_directory_evaluation_loads_gt_after_engine(self, tmp_path: Path):
        from scripts.generate_data import (
            write_bank_transactions_csv,
            write_ground_truth_json,
            write_payments_csv,
            write_settlements_csv,
        )

        generator = CleanDataGenerator(GeneratorConfig(num_records=40, seed=5))
        payments, settlements, banks = generator.generate_clean_data()
        injector = AnomalyInjector(GeneratorConfig(num_records=40, seed=5))
        gt = injector.inject_all_anomalies(payments, settlements, banks)

        write_payments_csv(payments, tmp_path / "payments.csv")
        write_settlements_csv(settlements, tmp_path / "settlement_recon.csv")
        write_bank_transactions_csv(banks, tmp_path / "bank_transactions.csv")
        write_ground_truth_json(gt, tmp_path / "ground_truth.json", seed=5, num_records=40)

        loaded_gt, seed, num_records = load_ground_truth(tmp_path / "ground_truth.json")
        assert seed == 5
        assert num_records == 40
        assert len(loaded_gt) == len(gt)

        report = evaluate_directory(tmp_path)
        assert report.seed == 5
        assert report.metrics.total_ground_truth_anomalies == len(gt)
        assert report.metrics.metric_definitions["detection_rate"]
        json.dumps(report.model_dump(mode="json"))


class TestMetricDefinitions:
    def test_rates_use_documented_formulas(self):
        run = fake_run(
            payments=[
                payment_result(ReconciliationStatus.MISSING_SETTLEMENT, payment_id="pay_001"),
                payment_result(ReconciliationStatus.RECONCILED, payment_id="pay_002"),
            ],
            batches=[batch_result(ReconciliationStatus.RECONCILED)],
        )
        anomalies = [
            gt_record(anomaly_id="anom_000001", related_ids={"payment_id": "pay_001"}),
            gt_record(
                anomaly_id="anom_000002",
                related_ids={"payment_id": "pay_002"},
                affected_entity_id="pay_002",
            ),
            gt_record(
                anomaly_id="anom_000003",
                related_ids={"payment_id": "pay_missing"},
                affected_entity_id="pay_missing",
            ),
        ]
        report = compare_run(run, anomalies)
        assert report.metrics.correctly_detected == 1
        assert report.metrics.incorrectly_classified == 1
        assert report.metrics.missed_anomalies == 1
        assert report.metrics.detection_rate == 2 / 3
        assert report.metrics.classification_accuracy == 0.5
        assert report.metrics.exact_recall == 1 / 3
