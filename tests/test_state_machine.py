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

    def stream_conversation(self, *, user_text: str, history):
        yield "I can"
        yield " help."


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


def make_controller(detections: list[Detection]) -> tuple[StateController, StubTTS]:
    tts = StubTTS()
    return (
        StateController(
            detector=StubDetector(detections),
            settings=Settings(),
            llm_client=StubLLM(),
            tts=tts,
            clock=StubClock(datetime(2024, 1, 1, 12, 0, 0)),
        ),
        tts,
    )


def test_state_machine_transitions_to_conversation_on_person_or_vehicle() -> None:
    controller, _ = make_controller([Detection("person", 0.9, (0, 0, 1, 1))])
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.CONVERSATION


def test_state_machine_transitions_to_announce_for_non_person_vehicle() -> None:
    controller, _ = make_controller([Detection("cat", 0.9, (0, 0, 1, 1))])
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.ANNOUNCE
    assert controller.complete_announce() == JarvisState.STANDBY


def test_conversation_turn_streams_to_tts_and_tracks_timestamps() -> None:
    controller, tts = make_controller([Detection("person", 0.9, (0, 0, 1, 1))])
    controller.start_conversation()
    result = controller.process_conversation_turn(user_text="status", t_start=1.0)

    assert result.assistant_text == "I can help."
    assert result.t_llm_first >= result.t_start
    assert result.t_tts_start >= result.t_llm_first
    assert tts.spoken[0] == "Hello. How can I help?"
    assert tts.spoken[1] == "I can help."
