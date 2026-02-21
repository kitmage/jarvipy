"""Jarvis Pi entry point and resilience loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from infra.config import load_dotenv, load_settings
from infra.errors import AudioDeviceUnavailableError, CameraDisconnectedError, LLMServiceError
from infra.logging import get_logger
from infra.recovery import BackoffPolicy, is_recoverable_error, retry_operation


@dataclass
class Subsystems:
    """Runtime subsystem hooks used by the resilient main loop."""

    camera_tick: Callable[[], None]
    audio_tick: Callable[[], None]
    llm_tick: Callable[[], None]


def run_startup_health_checks() -> tuple[bool, dict[str, bool]]:
    """Run lightweight startup checks for configuration and logging."""
    checks = {"config_loadable": False, "logger_writable": False}
    try:
        load_dotenv()
        load_settings()
        checks["config_loadable"] = True
        logger = get_logger()
        logger.info("startup health checks completed", extra={"event_type": "health_check", "metadata": checks})
        checks["logger_writable"] = True
    except Exception:
        return False, checks
    return all(checks.values()), checks


def run_resilient_cycle(subsystems: Subsystems) -> None:
    """Run one resilient cycle for camera/audio/llm subsystems with retries."""

    def run_with_retry(name: str, operation: Callable[[], None]) -> None:
        retry_operation(
            operation,
            should_retry=is_recoverable_error,
            max_attempts=3,
            backoff=BackoffPolicy(base_seconds=0.01, factor=2.0, max_seconds=0.05),
            sleeper=lambda _: None,
        )
        get_logger().info("subsystem tick ok", extra={"event_type": "subsystem_ok", "metadata": {"name": name}})

    run_with_retry("camera", subsystems.camera_tick)
    run_with_retry("audio", subsystems.audio_tick)
    run_with_retry("llm", subsystems.llm_tick)


def default_subsystems() -> Subsystems:
    """Default no-op subsystems used until hardware adapters are wired."""

    def camera_tick() -> None:
        return None

    def audio_tick() -> None:
        return None

    def llm_tick() -> None:
        return None

    return Subsystems(camera_tick=camera_tick, audio_tick=audio_tick, llm_tick=llm_tick)


def main() -> int:
    ok, checks = run_startup_health_checks()
    logger = get_logger()
    if not ok:
        logger.error("startup health checks failed", extra={"event_type": "health_check", "metadata": checks})
        return 1

    try:
        run_resilient_cycle(default_subsystems())
    except (CameraDisconnectedError, AudioDeviceUnavailableError, LLMServiceError) as exc:
        logger.error(
            "recoverable subsystem exhausted retries",
            extra={"event_type": "recovery_exhausted", "metadata": {"error": str(exc)}},
        )
    logger.info("jarvis initialized", extra={"event_type": "startup", "metadata": checks})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
