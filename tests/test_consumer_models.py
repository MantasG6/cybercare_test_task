import pytest
from pydantic import ValidationError

from consumer.models import Event


def test_accepts_valid_event():
    event = Event.model_validate({"event_type": "message", "event_payload": "hello"})

    assert event == Event(event_type="message", event_payload="hello")


@pytest.mark.parametrize(
    "payload",
    [
        {"event_type": 123, "event_payload": {}},
        {"event_type": 123, "event_payload": "hello"},
        {"event_type": "message", "event_payload": {}},
        {"event_type": "message"},
        {"event_payload": "hello"},
        {"event_type": "message", "event_payload": "hello", "extra": "x"},
    ],
)
def test_rejects_invalid_event(payload):
    with pytest.raises(ValidationError):
        Event.model_validate(payload)
