from datetime import time

import pytest

from infra.config import load_settings


def test_load_settings_defaults() -> None:
    settings = load_settings({})
    assert settings.cooldown_seconds == 8
    assert settings.announce_min_confidence == 0.60


def test_quiet_hours_cross_midnight() -> None:
    settings = load_settings({"QUIET_HOURS_START": "22:00", "QUIET_HOURS_END": "07:00"})
    assert settings.quiet_hours.contains(time(23, 30))
    assert settings.quiet_hours.contains(time(6, 45))
    assert not settings.quiet_hours.contains(time(12, 0))


def test_invalid_confidence_raises() -> None:
    with pytest.raises(ValueError):
        load_settings({"ANNOUNCE_MIN_CONFIDENCE": "1.2"})
