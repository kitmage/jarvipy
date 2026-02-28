import pytest

from infra.config import Settings
from infra.errors import CameraDisconnectedError
from main import build_subsystems, validate_runtime_readiness


class FailingWatcher:
    def poll(self) -> None:
        raise RuntimeError("camera unavailable")


def test_validate_runtime_readiness_allows_mock_mode_without_llm() -> None:
    settings = Settings(runtime_mock_mode=True, llm_endpoint="", llm_model="")
    validate_runtime_readiness(settings)


def test_validate_runtime_readiness_requires_llm_fields_in_production() -> None:
    settings = Settings(runtime_mock_mode=False, llm_endpoint="", llm_model="")
    with pytest.raises(ValueError):
        validate_runtime_readiness(settings)


def test_build_subsystems_mock_mode_ticks_noop() -> None:
    settings = Settings(runtime_mock_mode=True)
    subsystems = build_subsystems(settings)
    subsystems.camera_tick()
    subsystems.audio_tick()
    subsystems.llm_tick()


def test_build_subsystems_production_camera_runtime_error_translated() -> None:
    settings = Settings(
        runtime_mock_mode=False, llm_endpoint="http://llm.local", llm_model="x"
    )
    subsystems = build_subsystems(settings, motion_watcher=FailingWatcher())

    with pytest.raises(CameraDisconnectedError):
        subsystems.camera_tick()
