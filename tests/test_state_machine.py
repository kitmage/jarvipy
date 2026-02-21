from dataclasses import dataclass
from datetime import datetime

from infra.config import Settings
from state.state_machine import JarvisState, MotionSignal, StateController
from vision.detect_objects import Detection


class StubDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, frame_or_path: object) -> list[Detection]:
        return self._detections


class StubLLM:
    def complete_announce(self, *, objects: list[str], local_time: str, previous_event_summary: str) -> str:
        return '{"say":"Noted.","priority":"high"}'


@dataclass
class StubClock:
    now: datetime

    def now_local(self) -> datetime:
        return self.now


class StubTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        return None


def make_controller(detections: list[Detection]) -> StateController:
    return StateController(
        detector=StubDetector(detections),
        settings=Settings(),
        llm_client=StubLLM(),
        tts=StubTTS(),
        clock=StubClock(datetime(2024, 1, 1, 12, 0, 0)),
    )


def test_state_machine_transitions_to_conversation_on_person_or_vehicle() -> None:
    controller = make_controller([Detection("person", 0.9, (0, 0, 1, 1))])
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.CONVERSATION


def test_state_machine_transitions_to_announce_for_non_person_vehicle() -> None:
    controller = make_controller([Detection("cat", 0.9, (0, 0, 1, 1))])
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.ANNOUNCE
    assert controller.complete_announce() == JarvisState.STANDBY
