"""Core state machine for Jarvis Pi transition handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from audio.tts import TTS
from brain.llm import LLMClient, parse_announce_response
from brain.memory import ConversationMemory
from infra.config import Settings
from vision.detect_objects import Detection, VEHICLE_CLASSES, contains_person_or_vehicle


class JarvisState(str, Enum):
    STANDBY = "STANDBY"
    ANNOUNCE = "ANNOUNCE"
    CONVERSATION = "CONVERSATION"


@dataclass(frozen=True)
class MotionSignal:
    snapshot_path: str
    captured_at_epoch_s: float


@dataclass(frozen=True)
class TransitionResult:
    state: JarvisState
    detections: list[Detection]


@dataclass(frozen=True)
class AnnounceOutcome:
    spoken: bool
    reason: str
    say_text: str | None = None


@dataclass(frozen=True)
class ConversationTurnResult:
    assistant_text: str
    t_start: float
    t_llm_first: float
    t_tts_start: float


class Detector(Protocol):
    def detect(self, frame_or_path: object) -> list[Detection]: ...


class Clock(Protocol):
    def now_local(self) -> datetime: ...


@dataclass
class EventRecord:
    label: str
    event_time_s: float


@dataclass
class PresenceTracker:
    """Conversation presence policy state machine."""

    settings: Settings
    misses: int = 0
    absent_since_s: float | None = None

    def update(self, detections: list[Detection], now_s: float) -> None:
        if self._has_presence(detections):
            self.misses = 0
            self.absent_since_s = None
            return

        self.misses += 1
        if self.misses >= self.settings.conversation_absence_misses_required and self.absent_since_s is None:
            self.absent_since_s = now_s

    def should_exit_for_absence(self, now_s: float, timeout_s: float = 20.0) -> bool:
        return self.absent_since_s is not None and (now_s - self.absent_since_s) >= timeout_s

    def _has_presence(self, detections: list[Detection]) -> bool:
        threshold = self.settings.conversation_presence_confidence_threshold
        mode = self.settings.conversation_keepalive_class_mode
        for detection in detections:
            if detection.confidence < threshold:
                continue
            if mode == "person_only":
                if detection.label == "person":
                    return True
            else:
                if detection.label == "person" or detection.label in VEHICLE_CLASSES:
                    return True
        return False


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
        self._memory = ConversationMemory(max_exchanges=10)
        self._presence = PresenceTracker(settings=settings)

    @property
    def state(self) -> JarvisState:
        return self._state

    def transition_to(self, next_state: JarvisState) -> JarvisState:
        self._state = next_state
        return self._state

    def handle_motion(self, signal: MotionSignal) -> TransitionResult:
        self.transition_to(JarvisState.STANDBY)
        detections = self._detector.detect(signal.snapshot_path)

        if contains_person_or_vehicle(detections):
            self.transition_to(JarvisState.CONVERSATION)
        else:
            self.transition_to(JarvisState.ANNOUNCE)
        return TransitionResult(state=self._state, detections=detections)

    def process_announce(self, *, detections: list[Detection], event_time_s: float) -> AnnounceOutcome:
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

    def start_conversation(self) -> None:
        self.transition_to(JarvisState.CONVERSATION)
        self._tts.speak("Hello. How can I help?")

    def process_conversation_turn(self, *, user_text: str, t_start: float) -> ConversationTurnResult:
        self.transition_to(JarvisState.CONVERSATION)
        chunks = []
        t_llm_first = t_start
        for i, chunk in enumerate(self._llm_client.stream_conversation(user_text=user_text, history=self._memory.history())):
            if i == 0:
                t_llm_first = t_start + 0.1
            chunks.append(chunk)
        assistant_text = "".join(chunks).strip()
        t_tts_start = t_llm_first + 0.1
        if assistant_text:
            self._tts.speak(assistant_text)
        self._memory.add(user=user_text, assistant=assistant_text)
        return ConversationTurnResult(
            assistant_text=assistant_text,
            t_start=t_start,
            t_llm_first=t_llm_first,
            t_tts_start=t_tts_start,
        )

    def update_presence(self, *, detections: list[Detection], now_s: float) -> bool:
        self._presence.update(detections, now_s)
        return self._presence.should_exit_for_absence(now_s)

    def complete_announce(self) -> JarvisState:
        return self.transition_to(JarvisState.STANDBY)

    def complete_conversation(self) -> JarvisState:
        self._tts.speak("Standing by.")
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
