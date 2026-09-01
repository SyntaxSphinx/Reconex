"""Script to generate synthetic financial data with anomalies."""

import argparse
import csv
import json
from pathlib import Path
from typing import List

from backend.app.models import Payment, SettlementRecord, BankTransaction
from backend.app.models.anomaly import AnomalyRecord
from backend.app.generator import (
    GeneratorConfig,
    CleanDataGenerator,
    AnomalyInjector,
)


def write_payments_csv(payments: List[Payment], output_path: Path) -> None:
    """Write payments to CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "payment_id",
            "order_id",
            "customer_id",
            "amount",
            "currency",
            "payment_date",
            "status",
            "refund_amount",
        ])
        for p in payments:
            writer.writerow([
                p.payment_id,
                p.order_id,
                p.customer_id,
                p.amount,
                p.currency,
                p.payment_date.isoformat(),
                p.status.value,
                p.refund_amount,
            ])


def write_settlements_csv(settlements: List[SettlementRecord], output_path: Path) -> None:
    """Write settlement records to CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "entity_id",
            "type",
            "payment_id",
            "order_id",
            "settlement_id",
            "settlement_utr",
            "amount",
            "debit",
            "credit",
            "fee",
            "tax",
            "settled_at",
            "description",
        ])
        for s in settlements:
            writer.writerow([
                s.entity_id,
                s.type.value,
                s.payment_id or "",
                s.order_id or "",
                s.settlement_id,
                s.settlement_utr,
                s.amount,
                s.debit,
                s.credit,
                s.fee,
                s.tax,
                s.settled_at.isoformat(),
                s.description,
            ])


def write_bank_transactions_csv(
    bank_transactions: List[BankTransaction], output_path: Path
) -> None:
    """Write bank transactions to CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "bank_transaction_id",
            "transaction_date",
            "description",
            "amount",
            "transaction_type",
            "utr",
        ])
        for bt in bank_transactions:
            writer.writerow([
                bt.bank_transaction_id,
                bt.transaction_date.isoformat(),
                bt.description,
                bt.amount,
                bt.transaction_type.value,
                bt.utr or "",
            ])


def write_ground_truth_json(
    ground_truth: List[AnomalyRecord],
    output_path: Path,
    seed: int,
    num_records: int,
) -> None:
    """Write ground truth to JSON with no runtime-dependent fields."""
    data = {
        "seed": seed,
        "num_records": num_records,
        "total_anomalies": len(ground_truth),
        "anomalies": [gt.model_dump(mode="json") for gt in ground_truth],
    }
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic financial data for LedgerPilot"
    )
    parser.add_argument(
        "--records",
        type=int,
        default=1000,
        help="Number of payment records to generate (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Output directory for generated files (default: data/generated)",
    )
    parser.add_argument(
        "--no-anomalies",
        action="store_true",
        help="Generate clean data without injecting anomalies",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = GeneratorConfig(
        num_records=args.records,
        seed=args.seed,
    )

    print(f"Generating {args.records} synthetic records with seed {args.seed}...")

    generator = CleanDataGenerator(config)
    payments, settlements, bank_transactions = generator.generate_clean_data()

    print(f"Generated {len(payments)} payments")
    print(f"Generated {len(settlements)} settlement records")
    print(f"Generated {len(bank_transactions)} bank transactions")

    ground_truth: List[AnomalyRecord] = []
    if not args.no_anomalies:
        print("\nInjecting anomalies...")
        injector = AnomalyInjector(config)
        ground_truth = injector.inject_all_anomalies(payments, settlements, bank_transactions)
        print(f"Injected {len(ground_truth)} anomalies:")

        anomaly_counts: dict[str, int] = {}
        for gt in ground_truth:
            anomaly_type = gt.anomaly_type.value
            anomaly_counts[anomaly_type] = anomaly_counts.get(anomaly_type, 0) + 1

        for anomaly_type, count in sorted(anomaly_counts.items()):
            print(f"  - {anomaly_type}: {count}")

    print(f"\nWriting output files to {output_dir}/...")
    write_payments_csv(payments, output_dir / "payments.csv")
    write_settlements_csv(settlements, output_dir / "settlement_recon.csv")
    write_bank_transactions_csv(bank_transactions, output_dir / "bank_transactions.csv")

    if ground_truth:
        write_ground_truth_json(
            ground_truth,
            output_dir / "ground_truth.json",
            seed=args.seed,
            num_records=args.records,
        )

    print("\nGeneration complete!")
    print(f"  - {output_dir / 'payments.csv'}")
    print(f"  - {output_dir / 'settlement_recon.csv'}")
    print(f"  - {output_dir / 'bank_transactions.csv'}")
    if ground_truth:
        print(f"  - {output_dir / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
