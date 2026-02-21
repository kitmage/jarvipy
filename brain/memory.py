"""Conversation memory for rolling assistant/user context."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Exchange:
    """One user/assistant exchange."""

    user: str
    assistant: str


@dataclass
class ConversationMemory:
    """Bounded rolling memory retaining the last N exchanges."""

    max_exchanges: int = 10
    _items: list[Exchange] = field(default_factory=list)

    def add(self, *, user: str, assistant: str) -> None:
        self._items.append(Exchange(user=user, assistant=assistant))
        if len(self._items) > self.max_exchanges:
            self._items = self._items[-self.max_exchanges :]

    def history(self) -> list[Exchange]:
        return list(self._items)
