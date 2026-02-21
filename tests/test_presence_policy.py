from infra.config import Settings
from state.state_machine import PresenceTracker
from vision.detect_objects import Detection


def test_presence_policy_person_or_vehicle_timeline() -> None:
    tracker = PresenceTracker(
        settings=Settings(
            conversation_presence_confidence_threshold=0.65,
            conversation_absence_misses_required=3,
            conversation_keepalive_class_mode="person_or_vehicle",
        )
    )

    tracker.update([Detection("person", 0.78, (0, 0, 1, 1))], now_s=0)
    tracker.update([], now_s=2)  # miss #1
    tracker.update([Detection("bicycle", 0.72, (0, 0, 1, 1))], now_s=4)  # reset
    tracker.update([Detection("car", 0.60, (0, 0, 1, 1))], now_s=6)  # miss #1
    tracker.update([], now_s=8)  # miss #2
    tracker.update([], now_s=10)  # miss #3 -> absence counted
    assert tracker.absent_since_s == 10
    assert not tracker.should_exit_for_absence(18)

    tracker.update([Detection("person", 0.81, (0, 0, 1, 1))], now_s=18)  # reset
    assert tracker.absent_since_s is None

    tracker.update([], now_s=20)
    tracker.update([], now_s=22)
    tracker.update([], now_s=24)  # absence counted again
    assert tracker.absent_since_s == 24
    assert tracker.should_exit_for_absence(44)


def test_presence_policy_person_only_ignores_vehicles() -> None:
    tracker = PresenceTracker(
        settings=Settings(
            conversation_presence_confidence_threshold=0.65,
            conversation_absence_misses_required=1,
            conversation_keepalive_class_mode="person_only",
        )
    )
    tracker.update([Detection("car", 0.9, (0, 0, 1, 1))], now_s=0)
    assert tracker.absent_since_s == 0
