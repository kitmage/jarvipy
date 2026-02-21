"""LLM client contracts and ANNOUNCE response parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AnnounceLLMResponse:
    """Validated LLM response payload for ANNOUNCE mode."""

    say: str
    priority: str


class LLMClient(Protocol):
    """Protocol for LLM operations."""

    def complete_announce(self, *, objects: list[str], local_time: str, previous_event_summary: str) -> str: ...


def parse_announce_response(raw_response: str) -> AnnounceLLMResponse:
    """Parse strict ANNOUNCE JSON payload and validate required fields."""
    payload = json.loads(raw_response)
    if not isinstance(payload, dict):
        raise ValueError("ANNOUNCE response must be a JSON object")

    say = payload.get("say")
    priority = payload.get("priority")
    if not isinstance(say, str) or not say.strip():
        raise ValueError("ANNOUNCE response field 'say' must be a non-empty string")
    if priority not in {"normal", "high"}:
        raise ValueError("ANNOUNCE response field 'priority' must be 'normal' or 'high'")

    return AnnounceLLMResponse(say=say.strip(), priority=priority)
