from motion.motion_watch import MotionTrigger


def test_motion_trigger_requires_six_consecutive_frames() -> None:
    trigger = MotionTrigger(area_threshold=100, required_consecutive_frames=6, cooldown_seconds=8)
    now = 100.0
    for _ in range(5):
        assert not trigger.update(101, now)
        now += 1.0
    assert trigger.update(101, now)


def test_motion_trigger_cooldown_blocks_retrigger() -> None:
    trigger = MotionTrigger(area_threshold=10, required_consecutive_frames=2, cooldown_seconds=5)
    assert not trigger.update(11, 0.0)
    assert trigger.update(11, 1.0)

    assert not trigger.update(11, 2.0)
    assert not trigger.update(11, 3.0)

    assert trigger.update(11, 6.0)
