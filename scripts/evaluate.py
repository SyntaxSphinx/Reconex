"""CLI to evaluate reconciliation results against Phase 1 ground truth."""

import argparse
import json
from pathlib import Path

from backend.app.evaluation import evaluate_directory


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def print_report(report) -> None:
    metrics = report.metrics
    print("=" * 80)
    print("EVALUATION REPORT")
    print("=" * 80)
    print()
    if report.seed is not None:
        print(f"Seed:                         {report.seed}")
    if report.num_records is not None:
        print(f"Records:                      {report.num_records}")
    print()
    print("OVERALL")
    print(f"  Total GT anomalies:         {metrics.total_ground_truth_anomalies:>8}")
    print(f"  Correctly detected:         {metrics.correctly_detected:>8}")
    print(f"  Missed (false negatives):   {metrics.missed_anomalies:>8}")
    print(f"  Incorrectly classified:     {metrics.incorrectly_classified:>8}")
    print(f"  False positives:            {metrics.false_positives:>8}")
    print()
    print("RATES (defined in the JSON report under metrics.metric_definitions)")
    print(f"  Detection rate (recall):    {_pct(metrics.detection_rate):>8}")
    print(f"  Classification accuracy:    {_pct(metrics.classification_accuracy):>8}")
    print(f"  Exact recall:               {_pct(metrics.exact_recall):>8}")
    print()
    print("PER ANOMALY TYPE")
    print(f"  {'type':22s} {'gt':>6} {'correct':>8} {'missed':>8} {'wrong':>8}")
    for row in report.by_type:
        print(
            f"  {row.anomaly_type:22s} {row.ground_truth_count:6d} "
            f"{row.correctly_detected:8d} {row.missed:8d} {row.incorrectly_classified:8d}"
        )
    print()
    print(f"Downstream effects explained: {len(report.downstream_effects)}")
    print()

    if report.missed:
        print("MISSED")
        for item in report.missed:
            print(f"  {item.anomaly_id} {item.anomaly_type.value}: {item.miss_reason}")
        print()

    if report.incorrectly_classified:
        print("INCORRECTLY CLASSIFIED")
        for item in report.incorrectly_classified:
            print(
                f"  {item.anomaly_id} {item.anomaly_type.value}: "
                f"expected {item.expected_statuses}, observed {item.observed_status}"
            )
        print()

    if report.false_positive_details:
        print("FALSE POSITIVES")
        for item in report.false_positive_details:
            ref = item.result
            print(
                f"  {ref.level.value} {ref.primary_status.value} "
                f"payment={ref.payment_id or '-'} settlement={ref.settlement_id or '-'}"
            )
        print()

    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate deterministic reconciliation against ground_truth.json"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated"),
        help="Directory containing CSVs and ground_truth.json (default: data/generated)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the JSON evaluation report",
    )
    args = parser.parse_args()

    print(f"Evaluating {args.data_dir}...")
    report = evaluate_directory(args.data_dir)
    print_report(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report.model_dump(mode="json"), f, indent=2)
            f.write("\n")
        print(f"[OK] Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
