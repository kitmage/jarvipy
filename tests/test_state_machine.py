from state.state_machine import JarvisState, MotionSignal, StateController
from vision.detect_objects import Detection


class StubDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, frame_or_path: object) -> list[Detection]:
        return self._detections


def test_state_machine_transitions_to_conversation_on_person_or_vehicle() -> None:
    controller = StateController(detector=StubDetector([Detection("person", 0.9, (0, 0, 1, 1))]))
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.CONVERSATION


def test_state_machine_transitions_to_announce_for_non_person_vehicle() -> None:
    controller = StateController(detector=StubDetector([Detection("cat", 0.9, (0, 0, 1, 1))]))
    result = controller.handle_motion(MotionSignal(snapshot_path="/tmp/x.jpg", captured_at_epoch_s=1.0))
    assert result.state == JarvisState.ANNOUNCE
    assert controller.complete_announce() == JarvisState.STANDBY
