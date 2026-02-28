"""Jarvis Pi entry point and resilience loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from infra.config import Settings, load_dotenv, load_settings
from infra.errors import (
    AudioDeviceUnavailableError,
    CameraDisconnectedError,
    LLMServiceError,
)
from infra.logging import get_logger
from infra.recovery import BackoffPolicy, is_recoverable_error, retry_operation
from motion.motion_watch import MotionEvent, MotionWatcher


class MotionPoller(Protocol):
    def poll(self) -> MotionEvent | None: ...


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
        logger.info(
            "startup health checks completed",
            extra={"event_type": "health_check", "metadata": checks},
        )
        checks["logger_writable"] = True
    except Exception:
        return False, checks
    return all(checks.values()), checks


def validate_runtime_readiness(settings: Settings) -> None:
    """Validate required runtime settings for non-mock deployments."""
    if settings.runtime_mock_mode:
        return

    missing_fields = []
    if not settings.llm_endpoint:
        missing_fields.append("LLM_ENDPOINT")
    if not settings.llm_model:
        missing_fields.append("LLM_MODEL")

    if missing_fields:
        raise ValueError(
            "Missing required settings for production mode: "
            + ", ".join(missing_fields)
        )


def build_subsystems(
    settings: Settings, motion_watcher: MotionPoller | None = None
) -> Subsystems:
    """Build subsystem handlers for either mock or production-like runtime mode."""
    logger = get_logger()

    if settings.runtime_mock_mode:
        logger.warning(
            "running in mock mode; hardware subsystems are disabled",
            extra={"event_type": "runtime_mode", "metadata": {"mock_mode": True}},
        )

        return Subsystems(
            camera_tick=lambda: None,
            audio_tick=lambda: None,
            llm_tick=lambda: None,
        )

    watcher = motion_watcher or MotionWatcher(
        area_threshold=settings.motion_area_threshold,
        cooldown_seconds=settings.cooldown_seconds,
    )

    def camera_tick_prod() -> None:
        try:
            motion_event = watcher.poll()
        except RuntimeError as exc:
            raise CameraDisconnectedError(str(exc)) from exc
        if motion_event is not None:
            logger.info(
                "motion event captured",
                extra={
                    "event_type": "motion_event",
                    "metadata": {
                        "snapshot_path": motion_event.snapshot_path,
                        "captured_at_epoch_s": motion_event.captured_at_epoch_s,
                    },
                },
            )

    def audio_tick_prod() -> None:
        return None

    def llm_tick_prod() -> None:
        if not settings.llm_endpoint or not settings.llm_model:
            raise LLMServiceError("LLM endpoint/model is not configured")

    logger.info(
        "running in production mode; runtime subsystems initialized",
        extra={"event_type": "runtime_mode", "metadata": {"mock_mode": False}},
    )
    return Subsystems(
        camera_tick=camera_tick_prod,
        audio_tick=audio_tick_prod,
        llm_tick=llm_tick_prod,
    )


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
        get_logger().info(
            "subsystem tick ok",
            extra={"event_type": "subsystem_ok", "metadata": {"name": name}},
        )

    run_with_retry("camera", subsystems.camera_tick)
    run_with_retry("audio", subsystems.audio_tick)
    run_with_retry("llm", subsystems.llm_tick)


def main() -> int:
    ok, checks = run_startup_health_checks()
    logger = get_logger()
    if not ok:
        logger.error(
            "startup health checks failed",
            extra={"event_type": "health_check", "metadata": checks},
        )
        return 1

    settings = load_settings()
    try:
        validate_runtime_readiness(settings)
    except ValueError as exc:
        logger.error(
            "runtime configuration invalid",
            extra={"event_type": "runtime_config", "metadata": {"error": str(exc)}},
        )
        return 1

    try:
        run_resilient_cycle(build_subsystems(settings))
    except (
        CameraDisconnectedError,
        AudioDeviceUnavailableError,
        LLMServiceError,
    ) as exc:
        logger.error(
            "recoverable subsystem exhausted retries",
            extra={"event_type": "recovery_exhausted", "metadata": {"error": str(exc)}},
        )
    logger.info(
        "jarvis initialized", extra={"event_type": "startup", "metadata": checks}
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
