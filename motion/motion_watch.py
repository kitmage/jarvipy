"""Motion detection logic and camera watcher for Jarvis Pi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

try:
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None


@dataclass(frozen=True)
class MotionEvent:
    """Represents a triggered motion event with captured snapshot."""

    captured_at_epoch_s: float
    snapshot_path: str


class MonotonicClock(Protocol):
    """Clock protocol for deterministic testing."""

    def __call__(self) -> float: ...


class MotionTrigger:
    """Pure motion trigger logic using consecutive-frame thresholds and cooldown."""

    def __init__(
        self,
        *,
        area_threshold: float,
        required_consecutive_frames: int = 6,
        cooldown_seconds: float = 8.0,
    ) -> None:
        self.area_threshold = area_threshold
        self.required_consecutive_frames = required_consecutive_frames
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_hits = 0
        self._last_trigger_ts = float("-inf")

    def update(self, contour_area: float, now_s: float) -> bool:
        """Consume one frame metric and return True when motion is triggered."""
        if contour_area > self.area_threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0

        if self._consecutive_hits < self.required_consecutive_frames:
            return False

        if now_s - self._last_trigger_ts < self.cooldown_seconds:
            return False

        self._last_trigger_ts = now_s
        self._consecutive_hits = 0
        return True


class MotionWatcher:
    """OpenCV-backed motion watcher configured for low-power standby detection."""

    def __init__(
        self,
        *,
        area_threshold: int,
        cooldown_seconds: int,
        camera_index: int = 0,
        width: int = 320,
        height: int = 240,
        target_fps: int = 10,
        clock: MonotonicClock | None = None,
        snapshot_dir: str = "/tmp",
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.snapshot_dir = Path(snapshot_dir)
        self._clock = clock
        self._trigger = MotionTrigger(
            area_threshold=area_threshold,
            required_consecutive_frames=6,
            cooldown_seconds=cooldown_seconds,
        )

    def process_contour_area(self, contour_area: float, now_s: float | None = None) -> bool:
        """Test hook for non-OpenCV environments."""
        timestamp = now_s if now_s is not None else self._now_s()
        return self._trigger.update(contour_area=contour_area, now_s=timestamp)

    def poll(self) -> MotionEvent | None:
        """Poll a single camera frame and emit a motion event when trigger conditions are met."""
        if cv2 is None:
            raise RuntimeError("OpenCV is required for MotionWatcher.poll()")

        capture = cv2.VideoCapture(self.camera_index)
        try:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.target_fps)
            ok, frame = capture.read()
            if not ok:
                return None

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (21, 21), 0)
            if not hasattr(self, "_background"):
                self._background = blur
                return None

            frame_delta = cv2.absdiff(self._background, blur)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contour_area = max((cv2.contourArea(contour) for contour in contours), default=0.0)

            if not self.process_contour_area(contour_area=contour_area):
                return None

            snapshot_path = self._save_snapshot(frame)
            return MotionEvent(captured_at_epoch_s=self._now_s(), snapshot_path=snapshot_path)
        finally:
            capture.release()

    def _save_snapshot(self, frame: object) -> str:
        if cv2 is None:
            raise RuntimeError("OpenCV is required for snapshot saving")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        snapshot_path = str(self.snapshot_dir / f"motion_{timestamp}.jpg")
        cv2.imwrite(snapshot_path, frame)
        return snapshot_path

    def _now_s(self) -> float:
        if self._clock is not None:
            return self._clock()
        from time import monotonic

        return monotonic()
