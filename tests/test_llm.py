import pytest

from brain.llm import parse_announce_response


def test_parse_announce_response_accepts_strict_json() -> None:
    parsed = parse_announce_response('{"say":"Heads up","priority":"normal"}')
    assert parsed.say == "Heads up"
    assert parsed.priority == "normal"


@pytest.mark.parametrize(
    "raw",
    [
        'not json',
        '{"say":"", "priority":"normal"}',
        '{"say":"ok", "priority":"urgent"}',
        '[1,2,3]',
        '{"priority":"high"}',
    ],
)
def test_parse_announce_response_rejects_invalid_payloads(raw: str) -> None:
    with pytest.raises(Exception):
        parse_announce_response(raw)
