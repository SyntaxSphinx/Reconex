"""CLI script to run reconciliation on generated datasets."""

import argparse
import json
from pathlib import Path
from collections import defaultdict

from backend.app.reconciliation import CSVLoader, ReconciliationEngine, ReconciliationStatus


def format_paise(paise: int) -> str:
    """Format paise as INR."""
    rupees = paise / 100
    return f"Rs {rupees:,.2f}"


def _print_status_counts(status_counts: dict[str, int], total: int) -> None:
    for status_name, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {status_name:30s} {count:>6} ({pct:5.1f}%)")


def _print_example(example, heading: str) -> None:
    print(f"--- {heading} ---")
    print(f"Level:         {example.level.value}")
    print(f"Payment ID:    {example.evidence.payment_id or 'N/A'}")
    print(f"Order ID:      {example.evidence.order_id or 'N/A'}")
    print(f"Settlement ID: {example.evidence.settlement_id or 'N/A'}")
    print(f"Bank Txn ID:   {example.evidence.bank_transaction_id or 'N/A'}")
    print(f"Rule:          {example.evidence.rule_applied or 'N/A'}")
    print(f"Message:       {example.message or 'N/A'}")
    if example.evidence.expected_amount_paise is not None:
        print(f"Expected:      {format_paise(example.evidence.expected_amount_paise)}")
    if example.evidence.actual_amount_paise is not None:
        print(f"Actual:        {format_paise(example.evidence.actual_amount_paise)}")
    if example.evidence.variance_paise is not None:
        print(f"Variance:      {format_paise(abs(example.evidence.variance_paise))}")
    if example.secondary_findings:
        print(f"Secondary:     {', '.join(f.value for f in example.secondary_findings)}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Run reconciliation on generated datasets")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated"),
        help="Directory containing CSV files (default: data/generated)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional: Save detailed results to JSON file",
    )
    parser.add_argument(
        "--show-examples",
        action="store_true",
        help="Show one example for each status type",
    )

    args = parser.parse_args()

    print(f"Loading data from {args.data_dir}...")

    try:
        data = CSVLoader.load_all(args.data_dir)
    except Exception as e:
        print(f"Error loading data: {e}")
        return 1

    print(f"[OK] Loaded {len(data.payments)} payments")
    print(f"[OK] Loaded {len(data.settlements)} settlement lines")
    print(f"[OK] Loaded {len(data.bank_transactions)} bank transactions")
    print()

    print("Running reconciliation...")
    engine = ReconciliationEngine(data)
    run = engine.reconcile()
    summary = run.summary

    print()
    print("=" * 80)
    print("RECONCILIATION SUMMARY")
    print("=" * 80)
    print()

    print(f"Payments processed:          {summary.payments_processed:>8}")
    print(f"Settlement lines processed:  {summary.settlement_lines_processed:>8}")
    print(f"Settlement batches:          {summary.settlement_batches_processed:>8}")
    print(f"Bank transactions:           {summary.bank_transactions_processed:>8}")
    print()

    print("PAYMENT-LEVEL RESULTS")
    print(f"  Reconciled:                {summary.reconciled_count:>8}")
    print(f"  Pending:                   {summary.pending_count:>8}")
    print(f"  Exceptions:                {summary.exception_count:>8}")
    print()
    print("  Status breakdown:")
    _print_status_counts(summary.status_counts, summary.payments_processed)
    print()

    print("BATCH-LEVEL RESULTS")
    print(f"  Reconciled:                {summary.batch_reconciled_count:>8}")
    print(f"  Pending:                   {summary.batch_pending_count:>8}")
    print(f"  Exceptions:                {summary.batch_exception_count:>8}")
    print()
    print("  Status breakdown:")
    _print_status_counts(summary.batch_status_counts, summary.settlement_batches_processed)
    print()

    print(f"Total expected settlement:   {format_paise(summary.total_expected_settlement_paise):>15}")
    print(f"Total matched bank credits:  {format_paise(summary.total_matched_bank_paise):>15}")
    print(f"Total absolute variance:     {format_paise(summary.total_absolute_variance_paise):>15}")
    print()

    print(f"Processing duration:         {summary.processing_duration_seconds:>8.3f} seconds")
    print()

    if args.show_examples:
        print("=" * 80)
        print("PAYMENT-LEVEL EXAMPLES")
        print("=" * 80)
        print()

        by_status = defaultdict(list)
        for result in run.payment_results:
            by_status[result.primary_status].append(result)

        for status in ReconciliationStatus:
            examples = by_status.get(status, [])
            if examples:
                _print_example(examples[0], f"PAYMENT {status.value}")

        print("=" * 80)
        print("BATCH-LEVEL EXAMPLES")
        print("=" * 80)
        print()

        by_batch_status = defaultdict(list)
        for result in run.batch_results:
            by_batch_status[result.primary_status].append(result)

        for status in ReconciliationStatus:
            examples = by_batch_status.get(status, [])
            if examples:
                _print_example(examples[0], f"BATCH {status.value}")

        amount_mismatch_batches = by_batch_status.get(ReconciliationStatus.AMOUNT_MISMATCH, [])
        if amount_mismatch_batches:
            batch = amount_mismatch_batches[0]
            settlement_id = batch.evidence.settlement_id
            related_payments = [
                r for r in run.payment_results if r.evidence.settlement_id == settlement_id
            ]
            payment_statuses = defaultdict(int)
            for r in related_payments:
                payment_statuses[r.primary_status.value] += 1
            print("--- AFFECTED BATCH DETAIL ---")
            print(f"Settlement ID: {settlement_id}")
            print(f"Batch status:  {batch.primary_status.value}")
            print(f"Expected:      {batch.evidence.expected_amount_paise} paise")
            print(f"Actual:        {batch.evidence.actual_amount_paise} paise")
            print(f"Variance:      {batch.evidence.variance_paise} paise")
            print(f"Payments in batch: {len(related_payments)}")
            print(f"Payment statuses: {dict(payment_statuses)}")
            print()

    if args.output:
        print(f"Saving detailed results to {args.output}...")

        output_data = {
            "summary": summary.model_dump(mode="json"),
            "payment_results": [r.model_dump(mode="json") for r in run.payment_results],
            "batch_results": [r.model_dump(mode="json") for r in run.batch_results],
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"[OK] Saved {len(run.payment_results)} payment results and {len(run.batch_results)} batch results")
        print()

    print("=" * 80)
    print("Reconciliation complete.")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
