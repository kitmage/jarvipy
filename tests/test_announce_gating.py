from dataclasses import dataclass
from datetime import datetime

import pytest

from infra.config import Settings
from state.state_machine import AnnounceOutcome, StateController
from vision.detect_objects import Detection


class StubDetector:
    def detect(self, frame_or_path: object) -> list[Detection]:
        return []


class StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def complete_announce(self, *, objects: list[str], local_time: str, previous_event_summary: str) -> str:
        return self.response


class StubTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        return None


@dataclass
class StubClock:
    now: datetime

    def now_local(self) -> datetime:
        return self.now


def make_controller(*, settings: Settings, llm_response: str, now: datetime) -> tuple[StateController, StubTTS]:
    tts = StubTTS()
    controller = StateController(
        detector=StubDetector(),
        settings=settings,
        llm_client=StubLLM(llm_response),
        tts=tts,
        clock=StubClock(now),
    )
    return controller, tts


@pytest.mark.parametrize(
    ("now", "detections", "llm_response", "expected_reason", "expected_spoken"),
    [
        (
            datetime(2024, 1, 1, 2, 10, 0),
            [Detection("dog", 0.91, (0, 0, 1, 1))],
            '{"say":"Intruder?","priority":"high"}',
            "quiet_hours",
            False,
        ),
        (
            datetime(2024, 1, 1, 16, 45, 0),
            [Detection("unknown", 0.41, (0, 0, 1, 1))],
            '{"say":"I saw something","priority":"high"}',
            "low_confidence",
            False,
        ),
        (
            datetime(2024, 1, 1, 14, 20, 0),
            [Detection("cat", 0.82, (0, 0, 1, 1))],
            '{"say":"Cat detected","priority":"normal"}',
            "no_repeat_or_high_priority",
            False,
        ),
    ],
)
def test_announce_gating_failures(
    now: datetime,
    detections: list[Detection],
    llm_response: str,
    expected_reason: str,
    expected_spoken: bool,
) -> None:
    settings = Settings(
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        announce_min_confidence=0.60,
        announce_repeat_window_seconds=30,
    )
    controller, tts = make_controller(settings=settings, llm_response=llm_response, now=now)
    outcome = controller.process_announce(detections=detections, event_time_s=100.0)
    assert outcome.reason == expected_reason
    assert outcome.spoken is expected_spoken
    assert tts.spoken == []


def test_announce_gating_passes_on_repeated_object_with_normal_priority() -> None:
    settings = Settings(announce_repeat_window_seconds=30)
    controller, tts = make_controller(
        settings=settings,
        llm_response='{"say":"The cat is back.","priority":"normal"}',
        now=datetime(2024, 1, 1, 14, 20, 0),
    )
    first = controller.process_announce(
        detections=[Detection("cat", 0.82, (0, 0, 1, 1))],
        event_time_s=100.0,
    )
    second = controller.process_announce(
        detections=[Detection("cat", 0.83, (0, 0, 1, 1))],
        event_time_s=120.0,
    )
    assert first.spoken is False
    assert second == AnnounceOutcome(spoken=True, reason="spoken", say_text="The cat is back.")
    assert tts.spoken == ["The cat is back."]


def test_announce_gating_passes_on_high_priority_without_repeat() -> None:
    settings = Settings()
    controller, tts = make_controller(
        settings=settings,
        llm_response='{"say":"Please check the driveway.","priority":"high"}',
        now=datetime(2024, 1, 1, 14, 20, 0),
    )
    outcome = controller.process_announce(
        detections=[Detection("bicycle", 0.82, (0, 0, 1, 1))],
        event_time_s=100.0,
    )
    assert outcome.spoken is True
    assert outcome.reason == "spoken"
    assert tts.spoken == ["Please check the driveway."]
