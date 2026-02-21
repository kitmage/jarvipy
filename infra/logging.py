"""Structured logging utilities for Jarvis Pi."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit logs as JSON objects with a stable schema."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "event_type": getattr(record, "event_type", "log"),
            "state": getattr(record, "state", None),
            "session_id": getattr(record, "session_id", None),
            "message": record.getMessage(),
            "metadata": getattr(record, "metadata", {}),
        }
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "jarvis", primary_path: str = "/var/log/jarvis.log") -> logging.Logger:
    """Configure and return a structured application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = JsonFormatter()
    try:
        handler = logging.FileHandler(primary_path)
    except (OSError, PermissionError):
        fallback = "/tmp/jarvis.log"
        print(f"[jarvis] warning: cannot open {primary_path}; falling back to {fallback}")
        Path(fallback).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(fallback)

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
