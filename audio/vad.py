"""Voice activity detection contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class VADEvent:
    """Speech boundary event."""

    kind: str  # start|stop
    timestamp_s: float


class VADStream(Protocol):
    """Streaming VAD event source."""

    def events(self) -> Iterable[VADEvent]: ...
