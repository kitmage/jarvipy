from vision.detect_objects import Detection, ObjectDetector, contains_person_or_vehicle


class FakeInterpreter:
    def __init__(self) -> None:
        self._input = [{"index": 0}]
        self._output = [{"index": 0}, {"index": 1}, {"index": 2}]
        self._tensors = {
            0: [[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]],
            1: [[1, 2]],
            2: [[0.91, 0.49]],
        }

    def allocate_tensors(self) -> None:
        return None

    def get_input_details(self) -> list[dict]:
        return self._input

    def get_output_details(self) -> list[dict]:
        return self._output

    def set_tensor(self, index: int, value: object) -> None:
        self._last_input = (index, value)

    def invoke(self) -> None:
        return None

    def get_tensor(self, index: int):
        return self._tensors[index]


def test_object_detector_filters_by_confidence() -> None:
    detector = ObjectDetector(FakeInterpreter(), labels={1: "cat", 2: "person"}, min_confidence=0.5)
    detections = detector.detect(image_tensor=[[0]])
    assert len(detections) == 1
    assert detections[0].label == "cat"


def test_contains_person_or_vehicle() -> None:
    assert contains_person_or_vehicle([Detection("person", 0.9, (0, 0, 1, 1))])
    assert contains_person_or_vehicle([Detection("car", 0.8, (0, 0, 1, 1))])
    assert not contains_person_or_vehicle([Detection("cat", 0.9, (0, 0, 1, 1))])
