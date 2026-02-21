"""Smoke test for basic startup and health checks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import run_startup_health_checks


if __name__ == "__main__":
    ok, details = run_startup_health_checks()
    print(details)
    raise SystemExit(0 if ok else 1)
