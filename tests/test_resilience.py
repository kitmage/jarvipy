import pytest

from infra.errors import AudioDeviceUnavailableError, CameraDisconnectedError
from infra.recovery import BackoffPolicy, retry_operation
from main import Subsystems, run_resilient_cycle


def test_retry_operation_recovers_after_transient_failures() -> None:
    attempts = {"n": 0}

    def op() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise CameraDisconnectedError("camera down")
        return "ok"

    out = retry_operation(
        op,
        should_retry=lambda exc: isinstance(exc, CameraDisconnectedError),
        max_attempts=4,
        backoff=BackoffPolicy(base_seconds=0.0),
        sleeper=lambda _: None,
    )
    assert out == "ok"
    assert attempts["n"] == 3


def test_retry_operation_raises_after_exhaustion() -> None:
    def op() -> None:
        raise AudioDeviceUnavailableError("mic missing")

    with pytest.raises(AudioDeviceUnavailableError):
        retry_operation(
            op,
            should_retry=lambda exc: isinstance(exc, AudioDeviceUnavailableError),
            max_attempts=2,
            backoff=BackoffPolicy(base_seconds=0.0),
            sleeper=lambda _: None,
        )


def test_run_resilient_cycle_retries_each_subsystem() -> None:
    camera_attempts = {"n": 0}

    def camera_tick() -> None:
        camera_attempts["n"] += 1
        if camera_attempts["n"] == 1:
            raise CameraDisconnectedError("temporary")

    subsystems = Subsystems(
        camera_tick=camera_tick,
        audio_tick=lambda: None,
        llm_tick=lambda: None,
    )
    run_resilient_cycle(subsystems)
    assert camera_attempts["n"] == 2
