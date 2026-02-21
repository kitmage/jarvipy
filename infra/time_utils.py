"""Time helpers used by state and instrumentation logic."""

from __future__ import annotations

import time


def monotonic_seconds() -> float:
    """Return monotonic time in seconds."""
    return time.monotonic()
