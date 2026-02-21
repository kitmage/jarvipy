"""Core state machine scaffold for Jarvis Pi."""

from __future__ import annotations

from enum import Enum


class JarvisState(str, Enum):
    STANDBY = "STANDBY"
    ANNOUNCE = "ANNOUNCE"
    CONVERSATION = "CONVERSATION"


class StateController:
    """Owns state transitions independent from hardware integrations."""

    def __init__(self) -> None:
        self._state = JarvisState.STANDBY

    @property
    def state(self) -> JarvisState:
        return self._state

    def transition_to(self, next_state: JarvisState) -> JarvisState:
        self._state = next_state
        return self._state
