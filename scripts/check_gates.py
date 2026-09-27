#!/usr/bin/env python3
"""Battery threshold gate checker for CI pipeline.

Verifies that simulation/battery metrics meet or exceed required quality,
latency, and stability gates.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_F1_FAIL = 10
EXIT_AC1_FAIL = 11
EXIT_FLIP_FAIL = 12
EXIT_P99_FAIL = 13
EXIT_WALL_FAIL = 14
EXIT_GROUND_FAIL = 15

GATE_EXIT_CODES: dict[str, int] = {
    "F1": EXIT_F1_FAIL,
    "AC@1": EXIT_AC1_FAIL,
    "flip": EXIT_FLIP_FAIL,
    "p99": EXIT_P99_FAIL,
    "wall": EXIT_WALL_FAIL,
    "grounding": EXIT_GROUND_FAIL,
}


class BatteryMetrics:
    """Holds parsed battery metric collections."""

    def __init__(self) -> None:
        self.f1: list[float] = []
        self.ac1_intra: list[float] = []
        self.ac1_cross: list[float] = []
        self.ac1_overall: list[float] = []
        self.flip_by_partition: dict[str, list[float]] = {}
        self.p99: list[float] = []
        self.wall: list[float] = []
        self.grounding: list[float] = []


def is_float(val: str) -> bool:
    """Checks whether a string can be converted to float."""
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def classify_metric_name(name: str) -> tuple[str | None, str | None]:
    """Classifies a metric name into (category, subcategory/partition).

    Categories: 'f1', 'ac1', 'flip', 'p99', 'wall', 'grounding'.
    """
    s = name.strip()
    if not s:
        return (None, None)
    clean = s.lower().replace("@", "1").replace("-", "_").replace(" ", "_")

    # F1
    if clean in (
        "f1",
        "f_1",
        "f1_score",
        "f_score",
        "f1_macro",
        "f1_micro",
    ) or clean.startswith("f1_"):
        return ("f1", None)

    # AC@1
    if (
        "ac1" in clean
        or "ac_1" in clean
        or "accuracy_1" in clean
        or "accuracy1" in clean
    ):
        if "intra" in clean:
            return ("ac1", "intra")
        if "cross" in clean:
            return ("ac1", "cross")
        return ("ac1", "overall")

    # Flip
    if clean.startswith("flip"):
        raw_part = s[4:].strip(" _-()")
        part = raw_part if raw_part else "overall"
        return ("flip", part)

    # P99
    if clean in ("p99", "p99_latency", "latency_p99", "p99_s", "p99_sec", "p99_ms"):
        return ("p99", None)

    # Wall
    if clean in (
        "wall",
        "wall_s",
        "wall_time",
        "wall_total_s",
        "wall_sec",
        "wall_seconds",
        "elapsed",
        "runtime",
    ):
        return ("wall", None)

    # Grounding
    if clean in (
        "grounding",
        "ground",
        "grounding_rate",
        "ground_rate",
        "grounding_score",
    ) or clean.startswith(("grounding_", "ground_")):
        return ("grounding", None)

    return (None, None)


def _record_metric(
    metrics: BatteryMetrics,
    cat: str | None,
    subcat: str | None,
    val: float,
) -> None:
    """Appends value to appropriate metric bucket."""
    if cat == "f1":
        metrics.f1.append(val)
    elif cat == "ac1":
        if subcat == "intra":
            metrics.ac1_intra.append(val)
        elif subcat == "cross":
            metrics.ac1_cross.append(val)
        else:
            metrics.ac1_overall.append(val)
    elif cat == "flip":
        part = subcat if subcat else "overall"
        if part not in metrics.flip_by_partition:
            metrics.flip_by_partition[part] = []
        metrics.flip_by_partition[part].append(val)
    elif cat == "p99":
        metrics.p99.append(val)
    elif cat == "wall":
        metrics.wall.append(val)
    elif cat == "grounding":
        metrics.grounding.append(val)


def parse_csv_file(path: str) -> BatteryMetrics:
    """Parses battery metrics CSV supporting key-value and column tabular layouts."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    if path.endswith(".json"):
        raise ValueError("JSON input is not supported; CSV format required")

    metrics = BatteryMetrics()
    with open(path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        raw_rows = [
            row
            for row in reader
            if any(cell.strip() for cell in row)
            and not (row and row[0].strip().startswith("#"))
        ]

    if not raw_rows:
        raise ValueError(f"CSV file is empty: {path}")

    if raw_rows[0] and raw_rows[0][0].strip().startswith("{"):
        raise ValueError("JSON input is not supported; CSV format required")

    first_row = [c.strip() for c in raw_rows[0]]
    first_col_lower = first_row[0].lower()

    is_kv = False
    data_start = 0

    if first_col_lower in ("metric", "metric_name", "key", "gate", "name", "indicator"):
        is_kv = True
        data_start = 1
    elif len(first_row) == 2:
        cat0, _ = classify_metric_name(first_row[0])
        cat1, _ = classify_metric_name(first_row[1])
        if cat0 is not None and cat1 is None or is_float(first_row[1]):
            is_kv = True
            data_start = 0
        else:
            is_kv = False
            data_start = 1
    elif len(first_row) == 3 and is_float(first_row[-1]):
        is_kv = True
        data_start = 0

    if is_kv:
        for row_idx, row in enumerate(raw_rows[data_start:], start=data_start + 1):
            clean_row = [c.strip() for c in row if c.strip() != ""]
            if not clean_row:
                continue
            if len(clean_row) == 1:
                raise ValueError(
                    f"Line {row_idx}: invalid key-value row (only 1 element): {row}"
                )
            if len(clean_row) == 2:
                metric_str, val_str = clean_row[0], clean_row[1]
                if not is_float(val_str):
                    raise ValueError(
                        f"Line {row_idx}: non-numeric value '{val_str}' for metric '{metric_str}'"
                    )
                val = float(val_str)
                cat, subcat = classify_metric_name(metric_str)
                _record_metric(metrics, cat, subcat, val)
            else:
                col0, col1, col_last = clean_row[0], clean_row[1], clean_row[-1]
                if not is_float(col_last):
                    raise ValueError(
                        f"Line {row_idx}: non-numeric value '{col_last}' in row {row}"
                    )
                val = float(col_last)
                cat0, sub0 = classify_metric_name(col0)
                if cat0 is not None:
                    sub = col1 if (sub0 is None or sub0 == "overall") else sub0
                    _record_metric(metrics, cat0, sub, val)
                else:
                    cat1, sub1 = classify_metric_name(col1)
                    if cat1 is not None:
                        sub = col0 if (sub1 is None or sub1 == "overall") else sub1
                        _record_metric(metrics, cat1, sub, val)
    else:
        # Column Tabular format
        headers = first_row
        if len(raw_rows) < 2:
            raise ValueError(f"Tabular CSV contains header but no data rows: {path}")

        partition_col_idx: int | None = None
        for idx, h in enumerate(headers):
            if h.lower() in ("partition", "part", "line", "machine", "group", "cell"):
                partition_col_idx = idx
                break

        for row_idx, row in enumerate(raw_rows[1:], start=2):
            part_name = None
            if partition_col_idx is not None and partition_col_idx < len(row):
                part_name = row[partition_col_idx].strip()

            for col_idx, col_name in enumerate(headers):
                if col_idx == partition_col_idx:
                    continue
                if col_idx >= len(row):
                    continue
                val_str = row[col_idx].strip()
                if not val_str:
                    continue
                if not is_float(val_str):
                    raise ValueError(
                        f"Line {row_idx}: non-numeric value '{val_str}' in column '{col_name}'"
                    )
                val = float(val_str)
                cat, subcat = classify_metric_name(col_name)
                if cat == "ac1":
                    if (subcat is None or subcat == "overall") and part_name:
                        if "intra" in part_name.lower():
                            subcat = "intra"
                        elif "cross" in part_name.lower():
                            subcat = "cross"
                elif (
                    cat == "flip"
                    and (subcat is None or subcat == "overall")
                    and part_name
                ):
                    subcat = part_name
                _record_metric(metrics, cat, subcat, val)

    return metrics


def evaluate_gates(
    metrics: BatteryMetrics,
    f1_threshold: float,
    ac1_threshold: float,
    flip_threshold: float,
    p99_threshold: float,
    max_s_threshold: float,
    ground_threshold: float,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Evaluates all gates against parsed metrics.

    Returns:
        (failures, failed_gate_names)
        failures is a list of (gate_name, failure_description)
    """
    failures: list[tuple[str, str]] = []
    failed_gate_names: list[str] = []

    # 1. F1 >= f1_threshold (fail if F1 < f1_threshold)
    if not metrics.f1:
        failures.append(("F1", "F1 metric missing from CSV"))
        failed_gate_names.append("F1")
    else:
        min_f1 = min(metrics.f1)
        if min_f1 < f1_threshold:
            failures.append(("F1", f"F1 ({min_f1:.4f} < {f1_threshold:.4f})"))
            failed_gate_names.append("F1")

    # 2. AC@1 >= ac1_threshold for intra and cross (fail if AC@1 < ac1_threshold)
    ac1_failed = False
    # Intra
    if metrics.ac1_intra:
        min_intra = min(metrics.ac1_intra)
        if min_intra < ac1_threshold:
            failures.append(
                ("AC@1", f"AC@1 intra ({min_intra:.4f} < {ac1_threshold:.4f})")
            )
            ac1_failed = True
    elif metrics.ac1_overall:
        min_overall = min(metrics.ac1_overall)
        if min_overall < ac1_threshold:
            failures.append(("AC@1", f"AC@1 ({min_overall:.4f} < {ac1_threshold:.4f})"))
            ac1_failed = True
    else:
        failures.append(("AC@1", "AC@1 intra (or overall) metric missing from CSV"))
        ac1_failed = True

    # Cross
    if metrics.ac1_cross:
        min_cross = min(metrics.ac1_cross)
        if min_cross < ac1_threshold:
            failures.append(
                ("AC@1", f"AC@1 cross ({min_cross:.4f} < {ac1_threshold:.4f})")
            )
            ac1_failed = True
    elif metrics.ac1_overall:
        # ac1_overall covers cross if not separately specified; already checked above
        pass
    else:
        failures.append(("AC@1", "AC@1 cross metric missing from CSV"))
        ac1_failed = True

    if ac1_failed and "AC@1" not in failed_gate_names:
        failed_gate_names.append("AC@1")

    # 3. flip < flip_threshold per partition (fail if flip >= flip_threshold)
    if not metrics.flip_by_partition:
        failures.append(("flip", "flip metric missing from CSV"))
        failed_gate_names.append("flip")
    else:
        flip_failed = False
        for part, vals in sorted(metrics.flip_by_partition.items()):
            max_flip = max(vals)
            if max_flip >= flip_threshold:
                failures.append(
                    (
                        "flip",
                        f"flip partition '{part}' ({max_flip:.4f} >= {flip_threshold:.4f})",
                    )
                )
                flip_failed = True
        if flip_failed:
            failed_gate_names.append("flip")

    # 4. p99 <= p99_threshold (fail if p99 > p99_threshold)
    if not metrics.p99:
        failures.append(("p99", "p99 metric missing from CSV"))
        failed_gate_names.append("p99")
    else:
        max_p99 = max(metrics.p99)
        if max_p99 > p99_threshold:
            failures.append(("p99", f"p99 ({max_p99:.4f} > {p99_threshold:.4f})"))
            failed_gate_names.append("p99")

    # 5. wall < max_s (fail if wall >= max_s)
    if not metrics.wall:
        failures.append(("wall", "wall metric missing from CSV"))
        failed_gate_names.append("wall")
    else:
        max_wall = max(metrics.wall)
        if max_wall >= max_s_threshold:
            failures.append(
                ("wall", f"wall ({max_wall:.4f}s >= {max_s_threshold:.4f}s)")
            )
            failed_gate_names.append("wall")

    # 6. grounding >= ground_threshold (fail if grounding < ground_threshold)
    if not metrics.grounding:
        failures.append(("grounding", "grounding metric missing from CSV"))
        failed_gate_names.append("grounding")
    else:
        min_ground = min(metrics.grounding)
        if min_ground < ground_threshold:
            failures.append(
                ("grounding", f"grounding ({min_ground:.4f} < {ground_threshold:.4f})")
            )
            failed_gate_names.append("grounding")

    return failures, failed_gate_names


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Battery threshold gate checker for CI pipeline."
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=str,
        help="Path to battery metrics CSV file (required)",
    )
    parser.add_argument(
        "--f1",
        type=float,
        default=0.85,
        help="Minimum F1 score threshold (default: 0.85)",
    )
    parser.add_argument(
        "--ac1",
        type=float,
        default=0.70,
        help="Minimum AC@1 threshold for intra and cross partitions (default: 0.70)",
    )
    parser.add_argument(
        "--flip",
        type=float,
        default=0.40,
        help="Maximum flip rate threshold per partition (default: 0.40)",
    )
    parser.add_argument(
        "--p99",
        type=float,
        default=3.0,
        help="Maximum p99 latency threshold in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--ground",
        type=float,
        default=0.95,
        help="Minimum grounding threshold (default: 0.95)",
    )
    parser.add_argument(
        "--max-s",
        dest="max_s",
        type=float,
        default=600.0,
        help="Maximum wall clock time threshold in seconds (default: 600.0)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    start_time = time.monotonic()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        metrics = parse_csv_file(args.csv)
    except (FileNotFoundError, ValueError, OSError, csv.Error) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return EXIT_ERROR

    # On every run, emit wall=<seconds>s
    if metrics.wall:
        wall_sec = metrics.wall[0]
    else:
        wall_sec = time.monotonic() - start_time
    print(f"wall={wall_sec:.2f}s")

    failures, failed_gate_names = evaluate_gates(
        metrics=metrics,
        f1_threshold=args.f1,
        ac1_threshold=args.ac1,
        flip_threshold=args.flip,
        p99_threshold=args.p99,
        max_s_threshold=args.max_s,
        ground_threshold=args.ground,
    )

    if failures:
        for _gate_name, msg in failures:
            sys.stderr.write(f"GATE FAILURE: {msg}\n")
        sys.stderr.write(f"FAILED GATES: {', '.join(failed_gate_names)}\n")
        first_failed = failed_gate_names[0]
        return GATE_EXIT_CODES.get(first_failed, EXIT_ERROR)

    print("PASS: all battery gates green")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
