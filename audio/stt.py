"""Speech-to-text streaming contracts."""

from __future__ import annotations

from typing import Iterable, Protocol


class STTStream(Protocol):
    """Streaming STT transcript source."""

    def final_transcripts(self) -> Iterable[str]: ...
