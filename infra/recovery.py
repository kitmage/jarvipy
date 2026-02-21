"""Resilience and retry primitives for recoverable subsystem failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

from infra.errors import AudioDeviceUnavailableError, CameraDisconnectedError, LLMServiceError

T = TypeVar("T")


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class BackoffPolicy:
    base_seconds: float = 0.5
    factor: float = 2.0
    max_seconds: float = 5.0

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_seconds * (self.factor ** max(0, attempt - 1))
        return min(delay, self.max_seconds)


def retry_operation(
    operation: Callable[[], T],
    *,
    should_retry: Callable[[Exception], bool],
    max_attempts: int,
    backoff: BackoffPolicy,
    sleeper: Sleeper,
) -> T:
    """Retry an operation with bounded exponential backoff for recoverable failures."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            if not should_retry(exc):
                raise
            last_error = exc
            if attempt == max_attempts:
                break
            sleeper(backoff.delay_for_attempt(attempt))
    assert last_error is not None
    raise last_error


RECOVERABLE_ERRORS = (CameraDisconnectedError, LLMServiceError, AudioDeviceUnavailableError)


def is_recoverable_error(exc: Exception) -> bool:
    return isinstance(exc, RECOVERABLE_ERRORS)
