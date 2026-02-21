"""Core state machine for Jarvis Pi transition handling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from vision.detect_objects import Detection, contains_person_or_vehicle


class JarvisState(str, Enum):
    """Top-level runtime states."""

    STANDBY = "STANDBY"
    ANNOUNCE = "ANNOUNCE"
    CONVERSATION = "CONVERSATION"


@dataclass(frozen=True)
class MotionSignal:
    """Input event emitted by motion watcher."""

    snapshot_path: str
    captured_at_epoch_s: float


@dataclass(frozen=True)
class TransitionResult:
    """Result metadata after processing one motion event."""

    state: JarvisState
    detections: list[Detection]


class Detector(Protocol):
    """State machine dependency protocol for object detection."""

    def detect(self, frame_or_path: object) -> list[Detection]: ...


class StateController:
    """Owns transitions and delegates hardware concerns to dependencies."""

    def __init__(self, detector: Detector) -> None:
        self._state = JarvisState.STANDBY
        self._detector = detector

    @property
    def state(self) -> JarvisState:
        return self._state

    def transition_to(self, next_state: JarvisState) -> JarvisState:
        """Force a state transition."""
        self._state = next_state
        return self._state

    def handle_motion(self, signal: MotionSignal) -> TransitionResult:
        """Process motion event and route to conversation or announce paths."""
        self.transition_to(JarvisState.STANDBY)
        detections = self._detector.detect(signal.snapshot_path)

        if contains_person_or_vehicle(detections):
            self.transition_to(JarvisState.CONVERSATION)
        else:
            self.transition_to(JarvisState.ANNOUNCE)
        return TransitionResult(state=self._state, detections=detections)

    def complete_announce(self) -> JarvisState:
        """Return to standby after announce output (or silent skip)."""
        return self.transition_to(JarvisState.STANDBY)

    def complete_conversation(self) -> JarvisState:
        """Return to standby after conversation exit policy triggers."""
        return self.transition_to(JarvisState.STANDBY)
