"""Jarvis Pi entry point for slice 1 scaffold."""

from __future__ import annotations

from infra.config import load_dotenv, load_settings
from infra.logging import get_logger


def run_startup_health_checks() -> tuple[bool, dict[str, bool]]:
    """Run lightweight startup checks for configuration and logging."""
    checks = {
        "config_loadable": False,
        "logger_writable": False,
    }
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


def main() -> int:
    ok, checks = run_startup_health_checks()
    logger = get_logger()
    if not ok:
        logger.error(
            "startup health checks failed",
            extra={"event_type": "health_check", "metadata": checks},
        )
        return 1

    logger.info("jarvis scaffold initialized", extra={"event_type": "startup", "metadata": checks})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
