"""TTS contracts and simple in-memory adapter for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class TTS(Protocol):
    """Text-to-speech protocol."""

    def speak(self, text: str) -> None: ...

    def stop(self) -> None: ...


@dataclass
class InMemoryTTS:
    """Test TTS implementation that records spoken text."""

    spoken: list[str] = field(default_factory=list)

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        return None
