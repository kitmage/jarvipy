"""TFLite object detection abstractions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}


@dataclass(frozen=True)
class Detection:
    """Normalized object detection output."""

    label: str
    confidence: float
    bbox: tuple[float, float, float, float]


class TFLiteInterpreter(Protocol):
    """Protocol for TFLite interpreter compatibility and mocking."""

    def allocate_tensors(self) -> None: ...

    def get_input_details(self) -> list[dict]: ...

    def get_output_details(self) -> list[dict]: ...

    def set_tensor(self, index: int, value: object) -> None: ...

    def invoke(self) -> None: ...

    def get_tensor(self, index: int) -> object: ...


class ObjectDetector:
    """Runs TFLite SSD MobileNet style inference and normalizes detections."""

    def __init__(self, interpreter: TFLiteInterpreter, labels: dict[int, str], min_confidence: float = 0.0) -> None:
        self._interpreter = interpreter
        self._labels = labels
        self._min_confidence = min_confidence
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

    def detect(self, image_tensor: object) -> list[Detection]:
        """Run inference and return filtered detections."""
        self._interpreter.set_tensor(self._input_details[0]["index"], image_tensor)
        self._interpreter.invoke()

        boxes = self._interpreter.get_tensor(self._output_details[0]["index"])[0]
        classes = self._interpreter.get_tensor(self._output_details[1]["index"])[0]
        scores = self._interpreter.get_tensor(self._output_details[2]["index"])[0]

        detections: list[Detection] = []
        for bbox, class_id, score in zip(boxes, classes, scores):
            confidence = float(score)
            if confidence < self._min_confidence:
                continue
            label = self._labels.get(int(class_id), "unknown")
            ymin, xmin, ymax, xmax = (float(v) for v in bbox)
            detections.append(
                Detection(label=label, confidence=confidence, bbox=(xmin, ymin, xmax, ymax))
            )
        return detections


def contains_person_or_vehicle(detections: list[Detection]) -> bool:
    """Return True when detections include a person or configured vehicle class."""
    return any(det.label == "person" or det.label in VEHICLE_CLASSES for det in detections)
