"""Configuration loading and validation for Jarvis Pi."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class QuietHours:
    """Represents a local quiet-hours window."""

    start: time
    end: time

    def contains(self, current: time) -> bool:
        """Return True if current time is within quiet hours, including cross-midnight windows."""
        if self.start == self.end:
            return False
        if self.start < self.end:
            return self.start <= current < self.end
        return current >= self.start or current < self.end


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    llm_api_key: str = ""
    llm_endpoint: str = ""
    llm_model: str = ""
    motion_area_threshold: int = 500
    cooldown_seconds: int = 8
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    announce_min_confidence: float = 0.60
    announce_repeat_window_seconds: int = 30
    conversation_presence_confidence_threshold: float = 0.65
    conversation_absence_misses_required: int = 3
    conversation_keepalive_class_mode: str = "person_or_vehicle"

    @property
    def quiet_hours(self) -> QuietHours:
        return QuietHours(
            start=_parse_hhmm(self.quiet_hours_start),
            end=_parse_hhmm(self.quiet_hours_end),
        )


def load_dotenv(path: str = ".env") -> None:
    """Load .env key-value pairs into environment without overriding existing values."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Load and validate application settings from environment."""
    source = env or os.environ
    settings = Settings(
        llm_api_key=source.get("LLM_API_KEY", ""),
        llm_endpoint=source.get("LLM_ENDPOINT", ""),
        llm_model=source.get("LLM_MODEL", ""),
        motion_area_threshold=int(source.get("MOTION_AREA_THRESHOLD", 500)),
        cooldown_seconds=int(source.get("COOLDOWN_SECONDS", 8)),
        quiet_hours_start=source.get("QUIET_HOURS_START", "22:00"),
        quiet_hours_end=source.get("QUIET_HOURS_END", "07:00"),
        announce_min_confidence=float(source.get("ANNOUNCE_MIN_CONFIDENCE", 0.60)),
        announce_repeat_window_seconds=int(source.get("ANNOUNCE_REPEAT_WINDOW_SECONDS", 30)),
        conversation_presence_confidence_threshold=float(
            source.get("CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD", 0.65)
        ),
        conversation_absence_misses_required=int(source.get("CONVERSATION_ABSENCE_MISSES_REQUIRED", 3)),
        conversation_keepalive_class_mode=source.get(
            "CONVERSATION_KEEPALIVE_CLASS_MODE", "person_or_vehicle"
        ),
    )
    _validate(settings)
    return settings


def _parse_hhmm(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format '{value}', expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time value '{value}', expected HH:MM in 24-hour range")
    return time(hour=hour, minute=minute)


def _validate(settings: Settings) -> None:
    if settings.motion_area_threshold <= 0:
        raise ValueError("MOTION_AREA_THRESHOLD must be positive")
    if settings.cooldown_seconds <= 0:
        raise ValueError("COOLDOWN_SECONDS must be positive")
    if not 0.0 <= settings.announce_min_confidence <= 1.0:
        raise ValueError("ANNOUNCE_MIN_CONFIDENCE must be in [0, 1]")
    if settings.announce_repeat_window_seconds <= 0:
        raise ValueError("ANNOUNCE_REPEAT_WINDOW_SECONDS must be positive")
    if not 0.0 <= settings.conversation_presence_confidence_threshold <= 1.0:
        raise ValueError("CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD must be in [0, 1]")
    if settings.conversation_absence_misses_required <= 0:
        raise ValueError("CONVERSATION_ABSENCE_MISSES_REQUIRED must be positive")
    if settings.conversation_keepalive_class_mode not in {"person_or_vehicle", "person_only"}:
        raise ValueError("CONVERSATION_KEEPALIVE_CLASS_MODE must be person_or_vehicle or person_only")
    _parse_hhmm(settings.quiet_hours_start)
    _parse_hhmm(settings.quiet_hours_end)
