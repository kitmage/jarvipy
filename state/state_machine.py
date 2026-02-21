"""Core state machine for Jarvis Pi transition handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from audio.tts import TTS
from brain.llm import LLMClient, parse_announce_response
from infra.config import Settings
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


@dataclass(frozen=True)
class AnnounceOutcome:
    """Outcome of ANNOUNCE processing and gating decisions."""

    spoken: bool
    reason: str
    say_text: str | None = None


class Detector(Protocol):
    """State machine dependency protocol for object detection."""

    def detect(self, frame_or_path: object) -> list[Detection]: ...


class Clock(Protocol):
    """Clock protocol for deterministic tests."""

    def now_local(self) -> datetime: ...


@dataclass
class EventRecord:
    """Tracks non-person announce-relevant detections for repeat-window checks."""

    label: str
    event_time_s: float


class StateController:
    """Owns transitions and delegates hardware concerns to dependencies."""

    def __init__(
        self,
        detector: Detector,
        settings: Settings,
        llm_client: LLMClient,
        tts: TTS,
        clock: Clock,
    ) -> None:
        self._state = JarvisState.STANDBY
        self._detector = detector
        self._settings = settings
        self._llm_client = llm_client
        self._tts = tts
        self._clock = clock
        self._event_history: list[EventRecord] = []
        self._last_event_summary = "none"

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

    def process_announce(self, *, detections: list[Detection], event_time_s: float) -> AnnounceOutcome:
        """Run ANNOUNCE gating, invoke LLM JSON mode, and optionally speak via TTS."""
        self.transition_to(JarvisState.ANNOUNCE)

        if self._settings.quiet_hours.contains(self._clock.now_local().time()):
            self._record_event(detections, event_time_s)
            self.complete_announce()
            return AnnounceOutcome(spoken=False, reason="quiet_hours")

        non_person = [d for d in detections if d.label != "person"]
        if not non_person:
            self._record_event(detections, event_time_s)
            self.complete_announce()
            return AnnounceOutcome(spoken=False, reason="no_non_person_detection")

        top_non_person = max(non_person, key=lambda item: item.confidence)
        if top_non_person.confidence < self._settings.announce_min_confidence:
            self._record_event(detections, event_time_s)
            self.complete_announce()
            return AnnounceOutcome(spoken=False, reason="low_confidence")

        llm_raw = self._llm_client.complete_announce(
            objects=[f"{d.label}:{d.confidence:.2f}" for d in detections],
            local_time=self._clock.now_local().isoformat(),
            previous_event_summary=self._last_event_summary,
        )
        try:
            llm_response = parse_announce_response(llm_raw)
        except Exception:
            self._record_event(detections, event_time_s)
            self.complete_announce()
            return AnnounceOutcome(spoken=False, reason="invalid_llm_json")

        repeated = self._is_repeated_object(top_non_person.label, event_time_s)
        priority_high = llm_response.priority == "high"
        if not (repeated or priority_high):
            self._record_event(detections, event_time_s)
            self.complete_announce()
            return AnnounceOutcome(spoken=False, reason="no_repeat_or_high_priority")

        self._tts.speak(llm_response.say)
        self._record_event(detections, event_time_s)
        self._last_event_summary = f"spoke:{top_non_person.label}:{top_non_person.confidence:.2f}"
        self.complete_announce()
        return AnnounceOutcome(spoken=True, reason="spoken", say_text=llm_response.say)

    def complete_announce(self) -> JarvisState:
        """Return to standby after announce output (or silent skip)."""
        return self.transition_to(JarvisState.STANDBY)

    def complete_conversation(self) -> JarvisState:
        """Return to standby after conversation exit policy triggers."""
        return self.transition_to(JarvisState.STANDBY)

    def _is_repeated_object(self, label: str, event_time_s: float) -> bool:
        window_start = event_time_s - self._settings.announce_repeat_window_seconds
        matches = [
            event
            for event in self._event_history
            if event.label == label and event.event_time_s >= window_start
        ]
        return bool(matches)

    def _record_event(self, detections: list[Detection], event_time_s: float) -> None:
        non_person_labels = {d.label for d in detections if d.label != "person"}
        for label in non_person_labels:
            self._event_history.append(EventRecord(label=label, event_time_s=event_time_s))
        min_keep = event_time_s - self._settings.announce_repeat_window_seconds
        self._event_history = [event for event in self._event_history if event.event_time_s >= min_keep]
        if detections:
            top = max(detections, key=lambda item: item.confidence)
            self._last_event_summary = f"seen:{top.label}:{top.confidence:.2f}"
