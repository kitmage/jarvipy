"""Validate conversation latency from structured Jarvis logs."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LatencySample:
    """Timing triplet from one conversation turn."""

    t_start: float
    t_llm_first: float
    t_tts_start: float


@dataclass(frozen=True)
class ValidationResult:
    """Computed metrics and pass/fail status."""

    count: int
    p95: float
    max_latency: float
    missing_records: int
    passed: bool


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_samples(log_path: Path) -> tuple[list[LatencySample], int]:
    """Extract latency samples from a JSONL structured log file."""
    samples: list[LatencySample] = []
    missing_records = 0

    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        metadata = record.get("metadata") if isinstance(record, dict) else None
        source = metadata if isinstance(metadata, dict) else record

        t_start = _coerce_float(
            source.get("t_start") if isinstance(source, dict) else None
        )
        t_llm_first = _coerce_float(
            source.get("t_llm_first") if isinstance(source, dict) else None
        )
        t_tts_start = _coerce_float(
            source.get("t_tts_start") if isinstance(source, dict) else None
        )

        if t_start is None and t_llm_first is None and t_tts_start is None:
            continue

        if t_start is None or t_llm_first is None or t_tts_start is None:
            missing_records += 1
            continue

        samples.append(
            LatencySample(
                t_start=t_start, t_llm_first=t_llm_first, t_tts_start=t_tts_start
            )
        )

    return samples, missing_records


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Compute a percentile with linear interpolation."""
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * percentile
    lower_idx = int(math.floor(rank))
    upper_idx = int(math.ceil(rank))
    if lower_idx == upper_idx:
        return sorted_values[lower_idx]

    lower = sorted_values[lower_idx]
    upper = sorted_values[upper_idx]
    weight = rank - lower_idx
    return lower + (upper - lower) * weight


def validate(samples: list[LatencySample], missing_records: int) -> ValidationResult:
    """Evaluate samples against Slice 7 latency acceptance thresholds."""
    latencies = sorted(sample.t_tts_start - sample.t_start for sample in samples)
    p95 = _percentile(latencies, 0.95)
    max_latency = max(latencies) if latencies else math.nan

    passed = bool(
        latencies and missing_records == 0 and p95 < 3.0 and max_latency <= 3.5
    )

    return ValidationResult(
        count=len(latencies),
        p95=p95,
        max_latency=max_latency,
        missing_records=missing_records,
        passed=passed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Jarvis conversation latency from logs."
    )
    parser.add_argument(
        "log_path",
        nargs="?",
        default="/var/log/jarvis.log",
        help="Path to structured log file",
    )
    args = parser.parse_args()

    log_path = Path(args.log_path)
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 2

    samples, missing_records = extract_samples(log_path)
    result = validate(samples, missing_records)

    print(
        json.dumps(
            {
                "count": result.count,
                "missing_records": result.missing_records,
                "p95_tts_start_minus_start": result.p95,
                "max_tts_start_minus_start": result.max_latency,
                "passed": result.passed,
            },
            indent=2,
        )
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
