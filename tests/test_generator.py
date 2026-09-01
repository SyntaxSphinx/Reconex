"""Tests for synthetic data generator and anomaly injection."""

import ast
import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from backend.app.generator import (
    GeneratorConfig,
    AnomalyConfig,
    AnomalyRates,
    CleanDataGenerator,
    AnomalyInjector,
    allocate_count,
    counts_from_rates,
    cap_anomaly_counts,
)
from backend.app.generator import clean_generator as clean_generator_module
from backend.app.generator import anomaly_injector as anomaly_injector_module
from backend.app.generator.config import GeneratorConfig as GeneratorConfigClass
from backend.app.models import (
    Payment,
    PaymentStatus,
    SettlementRecord,
    BankTransaction,
    SettlementEntityType,
)
from backend.app.models.anomaly import AnomalyType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILES = (
    "payments.csv",
    "settlement_recon.csv",
    "bank_transactions.csv",
    "ground_truth.json",
)


def _generate(num_records: int, seed: int, anomaly_config: AnomalyConfig | None = None):
    config = GeneratorConfig(
        num_records=num_records,
        seed=seed,
        anomaly_config=anomaly_config,
    )
    payments, settlements, bank_txns = CleanDataGenerator(config).generate_clean_data()
    return config, payments, settlements, bank_txns


def _inject(config: GeneratorConfig, payments, settlements, bank_txns):
    injector = AnomalyInjector(config)
    ground_truth = injector.inject_all_anomalies(payments, settlements, bank_txns)
    return injector, ground_truth


def test_deterministic_generation():
    """Same seed produces identical clean data, not just the first payment."""
    config1 = GeneratorConfig(num_records=100, seed=42)
    config2 = GeneratorConfig(num_records=100, seed=42)

    payments1, settlements1, bank_txns1 = CleanDataGenerator(config1).generate_clean_data()
    payments2, settlements2, bank_txns2 = CleanDataGenerator(config2).generate_clean_data()

    assert [p.model_dump() for p in payments1] == [p.model_dump() for p in payments2]
    assert [s.model_dump() for s in settlements1] == [s.model_dump() for s in settlements2]
    assert [b.model_dump() for b in bank_txns1] == [b.model_dump() for b in bank_txns2]


def test_different_seeds_produce_different_data():
    """Different seeds produce different datasets."""
    config1 = GeneratorConfig(num_records=100, seed=42)
    config2 = GeneratorConfig(num_records=100, seed=43)

    payments1, _, _ = CleanDataGenerator(config1).generate_clean_data()
    payments2, _, _ = CleanDataGenerator(config2).generate_clean_data()

    assert payments1[0].payment_id != payments2[0].payment_id
    assert [p.amount for p in payments1] != [p.amount for p in payments2]


def test_unique_payment_ids():
    payments, _, _ = CleanDataGenerator(GeneratorConfig(num_records=100, seed=42)).generate_clean_data()
    payment_ids = [p.payment_id for p in payments]
    assert len(payment_ids) == len(set(payment_ids))


def test_unique_order_ids():
    payments, _, _ = CleanDataGenerator(GeneratorConfig(num_records=100, seed=42)).generate_clean_data()
    order_ids = [p.order_id for p in payments]
    assert len(order_ids) == len(set(order_ids))


def test_unique_settlement_entity_ids():
    _, settlements, _ = CleanDataGenerator(GeneratorConfig(num_records=100, seed=42)).generate_clean_data()
    entity_ids = [s.entity_id for s in settlements]
    assert len(entity_ids) == len(set(entity_ids))


def test_unique_bank_transaction_ids():
    _, _, bank_txns = CleanDataGenerator(GeneratorConfig(num_records=100, seed=42)).generate_clean_data()
    bank_ids = [b.bank_transaction_id for b in bank_txns]
    assert len(bank_ids) == len(set(bank_ids))
    assert len(bank_ids) >= 1


def test_payments_are_captured():
    payments, _, _ = CleanDataGenerator(GeneratorConfig(num_records=100, seed=42)).generate_clean_data()
    assert all(p.status == PaymentStatus.CAPTURED for p in payments)
    assert all(p.refund_amount == 0 for p in payments)


def test_amounts_are_integers():
    payments, settlements, bank_txns = CleanDataGenerator(
        GeneratorConfig(num_records=100, seed=42)
    ).generate_clean_data()

    for p in payments:
        assert type(p.amount) is int
        assert type(p.refund_amount) is int

    for s in settlements:
        assert type(s.amount) is int
        assert type(s.credit) is int
        assert type(s.debit) is int
        assert type(s.fee) is int
        assert type(s.tax) is int

    for bt in bank_txns:
        assert type(bt.amount) is int


def test_fee_and_tax_use_integer_formula():
    config = GeneratorConfig(num_records=100, seed=42)
    _, settlements, _ = CleanDataGenerator(config).generate_clean_data()
    for settlement in settlements:
        expected_fee = settlement.amount * 18 // 1000
        expected_tax = expected_fee * 18 // 100
        assert settlement.fee == expected_fee
        assert settlement.tax == expected_tax
        assert settlement.credit == settlement.amount - settlement.fee - settlement.tax
        assert settlement.debit == 0


def _assert_no_float_constants(func) -> None:
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    floats = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ]
    assert floats == [], f"{func.__qualname__} contains float literals: {floats}"


def test_monetary_functions_have_no_float_literals():
    """Fee, tax, variance, and refund math must not use float literals."""
    _assert_no_float_constants(GeneratorConfigClass.calculate_fee)
    _assert_no_float_constants(GeneratorConfigClass.calculate_tax)
    _assert_no_float_constants(CleanDataGenerator._calculate_fee_and_tax)
    _assert_no_float_constants(CleanDataGenerator._generate_amount)
    _assert_no_float_constants(AnomalyInjector.inject_amount_mismatch)
    _assert_no_float_constants(AnomalyInjector.inject_refund_mismatch)
    _assert_no_float_constants(allocate_count)
    _assert_no_float_constants(counts_from_rates)

    money_source = inspect.getsource(clean_generator_module) + inspect.getsource(anomaly_injector_module)
    tree = ast.parse(money_source)
    banned_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"uniform", "random", "gauss"}:
            banned_calls.append(node.attr)
    assert banned_calls == []


def test_generator_supports_different_record_counts():
    for size in (50, 100, 500):
        payments, _, _ = CleanDataGenerator(
            GeneratorConfig(num_records=size, seed=42)
        ).generate_clean_data()
        assert len(payments) == size


def test_anomaly_rates_scale_with_dataset_size():
    rates = AnomalyRates()
    counts_1000 = counts_from_rates(1000, rates)
    counts_100 = counts_from_rates(100, rates)

    assert counts_1000.total_anomalies == 35
    assert 30 <= counts_1000.total_anomalies <= 40
    assert counts_100.missing_settlement == 1
    assert counts_100.missing_bank_credit == 1
    assert counts_100.amount_mismatch == 1
    assert counts_100.total_anomalies == 6

    capped = cap_anomaly_counts(
        counts_100,
        payment_settlement_count=100,
        bank_count=2,
    )
    assert capped.missing_bank_credit == 1
    assert capped.amount_mismatch == 0
    assert capped.missing_bank_credit + capped.amount_mismatch <= 1


def test_source_records_remain_model_valid_after_anomalies():
    config, payments, settlements, bank_txns = _generate(100, 42)
    _inject(config, payments, settlements, bank_txns)

    for payment in payments:
        assert Payment.model_validate(payment.model_dump())
    for settlement in settlements:
        assert SettlementRecord.model_validate(settlement.model_dump())
    for bank_txn in bank_txns:
        assert BankTransaction.model_validate(bank_txn.model_dump())


def test_ground_truth_one_to_one_with_injections():
    config, payments, settlements, bank_txns = _generate(1000, 42)
    injector, ground_truth = _inject(config, payments, settlements, bank_txns)

    assert len(ground_truth) == injector.counts.total_anomalies
    assert len({gt.anomaly_id for gt in ground_truth}) == len(ground_truth)

    pay_ids = {p.payment_id for p in payments}
    entity_ids = {s.entity_id for s in settlements}
    bank_ids = {b.bank_transaction_id for b in bank_txns}

    type_counts = {t: 0 for t in AnomalyType}
    for record in ground_truth:
        type_counts[record.anomaly_type] += 1
        if record.anomaly_type == AnomalyType.MISSING_SETTLEMENT:
            assert record.affected_entity_id in pay_ids
            assert record.related_ids["removed_entity_id"] not in entity_ids
            related_bank = record.related_ids["related_bank_transaction_id"]
            assert related_bank in bank_ids
            assert "settlement_id" in record.related_ids
        elif record.anomaly_type == AnomalyType.MISSING_BANK_CREDIT:
            assert record.affected_entity_id not in bank_ids
            for entity_id in record.related_ids["affected_entity_ids"]:
                assert entity_id in entity_ids
        elif record.anomaly_type == AnomalyType.AMOUNT_MISMATCH:
            bank = next(b for b in bank_txns if b.bank_transaction_id == record.affected_entity_id)
            assert bank.amount == record.related_ids["modified_amount"]
            original = record.related_ids["original_amount"]
            percent = record.related_ids["percent"]
            assert 1 <= percent <= 10
            expected_abs = original * percent // 100
            if expected_abs == 0:
                expected_abs = 1
            assert abs(record.variance) == expected_abs or abs(record.variance) == 1
        elif record.anomaly_type == AnomalyType.DUPLICATE:
            assert record.related_ids["original_entity_id"] in entity_ids
            assert record.related_ids["duplicate_entity_id"] in entity_ids
        elif record.anomaly_type == AnomalyType.REFUND_MISMATCH:
            payment = next(p for p in payments if p.payment_id == record.related_ids["payment_id"])
            refund = next(s for s in settlements if s.entity_id == record.related_ids["refund_entity_id"])
            assert payment.refund_amount == record.related_ids["payment_refund_amount"]
            assert refund.amount == record.related_ids["settlement_refund_amount"]
            assert payment.refund_amount != refund.amount
            assert refund.type == SettlementEntityType.REFUND
        elif record.anomaly_type == AnomalyType.UNMATCHED_REFERENCE:
            settlement = next(s for s in settlements if s.entity_id == record.affected_entity_id)
            assert settlement.settlement_utr == record.related_ids["corrupted_utr"]
            assert settlement.settlement_id == record.related_ids["settlement_id"]

    assert type_counts[AnomalyType.MISSING_SETTLEMENT] == injector.counts.missing_settlement
    assert type_counts[AnomalyType.MISSING_BANK_CREDIT] == injector.counts.missing_bank_credit
    assert type_counts[AnomalyType.AMOUNT_MISMATCH] == injector.counts.amount_mismatch
    assert type_counts[AnomalyType.DUPLICATE] == injector.counts.duplicate
    assert type_counts[AnomalyType.REFUND_MISMATCH] == injector.counts.refund_mismatch
    assert type_counts[AnomalyType.UNMATCHED_REFERENCE] == injector.counts.unmatched_reference


def test_missing_settlement_anomaly():
    config, payments, settlements, bank_txns = _generate(
        100,
        42,
        AnomalyConfig(missing_settlement=5, missing_bank_credit=0, amount_mismatch=0, duplicate=0, refund_mismatch=0, unmatched_reference=0),
    )
    original_settlement_count = len(settlements)
    original_bank_ids = {b.bank_transaction_id for b in bank_txns}
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    missing = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.MISSING_SETTLEMENT]
    assert len(missing) == 5
    assert len(settlements) == original_settlement_count - 5
    assert {b.bank_transaction_id for b in bank_txns} == original_bank_ids

    for record in missing:
        assert any(p.payment_id == record.affected_entity_id for p in payments)
        assert all(s.entity_id != record.related_ids["removed_entity_id"] for s in settlements)
        assert record.related_ids["related_bank_transaction_id"] in original_bank_ids
        assert record.related_ids["settlement_id"]


def test_missing_bank_credit_anomaly():
    config, payments, settlements, bank_txns = _generate(
        1000,
        42,
        AnomalyConfig(missing_settlement=0, missing_bank_credit=5, amount_mismatch=0, duplicate=0, refund_mismatch=0, unmatched_reference=0),
    )
    original_bank_count = len(bank_txns)
    original_settlement_count = len(settlements)
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    missing = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.MISSING_BANK_CREDIT]
    assert len(missing) == 5
    assert len(bank_txns) == original_bank_count - 5
    assert len(settlements) == original_settlement_count

    remaining_ids = {b.bank_transaction_id for b in bank_txns}
    for record in missing:
        assert record.affected_entity_id not in remaining_ids
        assert record.related_ids["affected_entity_ids"]
        assert all(
            any(s.entity_id == entity_id for s in settlements)
            for entity_id in record.related_ids["affected_entity_ids"]
        )


def test_amount_mismatch_anomaly():
    config, payments, settlements, bank_txns = _generate(
        1000,
        42,
        AnomalyConfig(missing_settlement=0, missing_bank_credit=0, amount_mismatch=5, duplicate=0, refund_mismatch=0, unmatched_reference=0),
    )
    original_amounts = {b.bank_transaction_id: b.amount for b in bank_txns}
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    mismatches = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.AMOUNT_MISMATCH]
    assert len(mismatches) == 5

    changed_ids = {gt.affected_entity_id for gt in mismatches}
    for record in mismatches:
        bank = next(b for b in bank_txns if b.bank_transaction_id == record.affected_entity_id)
        assert bank.amount != original_amounts[bank.bank_transaction_id]
        assert bank.amount == record.related_ids["modified_amount"]
        assert type(record.variance) is int
        assert record.variance != 0
        assert 1 <= record.related_ids["percent"] <= 10

    unchanged = [b for b in bank_txns if b.bank_transaction_id not in changed_ids]
    assert unchanged
    for bank in unchanged:
        assert bank.amount == original_amounts[bank.bank_transaction_id]


def test_duplicate_anomaly():
    config, payments, settlements, bank_txns = _generate(
        100,
        42,
        AnomalyConfig(missing_settlement=0, missing_bank_credit=0, amount_mismatch=0, duplicate=3, refund_mismatch=0, unmatched_reference=0),
    )
    original_count = len(settlements)
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    duplicates = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.DUPLICATE]
    assert len(duplicates) == 3
    assert len(settlements) == original_count + 3
    for record in duplicates:
        original = next(s for s in settlements if s.entity_id == record.related_ids["original_entity_id"])
        duplicate = next(s for s in settlements if s.entity_id == record.related_ids["duplicate_entity_id"])
        assert original.payment_id == duplicate.payment_id
        assert original.amount == duplicate.amount
        assert original.entity_id != duplicate.entity_id


def test_refund_mismatch_anomaly():
    config, payments, settlements, bank_txns = _generate(
        100,
        42,
        AnomalyConfig(missing_settlement=0, missing_bank_credit=0, amount_mismatch=0, duplicate=0, refund_mismatch=3, unmatched_reference=0),
    )
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    refunds = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.REFUND_MISMATCH]
    assert len(refunds) == 3

    refund_rows = [s for s in settlements if s.type == SettlementEntityType.REFUND]
    assert len(refund_rows) == 3

    for record in refunds:
        payment = next(p for p in payments if p.payment_id == record.related_ids["payment_id"])
        refund_row = next(s for s in settlements if s.entity_id == record.related_ids["refund_entity_id"])
        assert payment.refund_amount > 0
        assert payment.refund_amount == record.related_ids["payment_refund_amount"]
        assert refund_row.type == SettlementEntityType.REFUND
        assert refund_row.payment_id == payment.payment_id
        assert refund_row.order_id == payment.order_id
        assert refund_row.amount == record.related_ids["settlement_refund_amount"]
        assert refund_row.debit == refund_row.amount
        assert payment.refund_amount != refund_row.amount
        assert record.variance == refund_row.amount - payment.refund_amount
        assert record.related_ids["settlement_id"] == refund_row.settlement_id
        assert record.related_ids["settlement_id"] != refund_row.entity_id


def test_unmatched_reference_anomaly():
    config, payments, settlements, bank_txns = _generate(
        100,
        42,
        AnomalyConfig(missing_settlement=0, missing_bank_credit=0, amount_mismatch=0, duplicate=0, refund_mismatch=0, unmatched_reference=3),
    )
    original_utrs = {s.entity_id: s.settlement_utr for s in settlements}
    _, ground_truth = _inject(config, payments, settlements, bank_txns)

    unmatched = [gt for gt in ground_truth if gt.anomaly_type == AnomalyType.UNMATCHED_REFERENCE]
    assert len(unmatched) == 3

    changed_ids = {gt.affected_entity_id for gt in unmatched}
    for record in unmatched:
        settlement = next(s for s in settlements if s.entity_id == record.affected_entity_id)
        assert settlement.settlement_utr == record.related_ids["corrupted_utr"]
        assert settlement.settlement_utr != record.related_ids["original_utr"]
        assert record.related_ids["entity_id"] == settlement.entity_id
        assert record.related_ids["settlement_id"] == settlement.settlement_id

    for settlement in settlements:
        if settlement.entity_id not in changed_ids:
            assert settlement.settlement_utr == original_utrs[settlement.entity_id]


def test_sample_dataset_retains_at_least_one_bank_transaction():
    config, payments, settlements, bank_txns = _generate(100, 42)
    clean_bank_count = len(bank_txns)
    injector, ground_truth = _inject(config, payments, settlements, bank_txns)

    assert len(payments) == 100
    assert len(settlements) >= 1
    assert clean_bank_count >= 1
    assert len(bank_txns) >= 1

    removed_banks = {
        gt.affected_entity_id
        for gt in ground_truth
        if gt.anomaly_type == AnomalyType.MISSING_BANK_CREDIT
    }
    mismatched_banks = {
        gt.affected_entity_id
        for gt in ground_truth
        if gt.anomaly_type == AnomalyType.AMOUNT_MISMATCH
    }
    clean_banks = [
        b
        for b in bank_txns
        if b.bank_transaction_id not in removed_banks
        and b.bank_transaction_id not in mismatched_banks
    ]
    assert clean_banks

    present_types = {gt.anomaly_type for gt in ground_truth}
    assert AnomalyType.MISSING_SETTLEMENT in present_types
    assert AnomalyType.MISSING_BANK_CREDIT in present_types
    assert AnomalyType.DUPLICATE in present_types
    assert AnomalyType.REFUND_MISMATCH in present_types
    assert AnomalyType.UNMATCHED_REFERENCE in present_types


def test_cli_deterministic_across_independent_processes(tmp_path):
    """Same CLI parameters must produce byte-for-byte identical artifacts."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    def run(output_dir: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.generate_data",
                "--records",
                "1000",
                "--seed",
                "42",
                "--output-dir",
                str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    run(dir_a)
    run(dir_b)

    for filename in OUTPUT_FILES:
        bytes_a = (dir_a / filename).read_bytes()
        bytes_b = (dir_b / filename).read_bytes()
        assert bytes_a == bytes_b, f"{filename} differed across processes"
        assert bytes_a, f"{filename} was empty"

    gt = json.loads((dir_a / "ground_truth.json").read_text(encoding="utf-8"))
    assert "generated_at" not in gt
    assert gt["seed"] == 42
    assert gt["num_records"] == 1000
    assert gt["total_anomalies"] == len(gt["anomalies"])
