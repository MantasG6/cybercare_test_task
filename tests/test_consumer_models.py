import pytest
from pydantic import ValidationError

from consumer.models import Event


def test_model_validate_should_return_event_when_fields_are_strings():
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
def test_model_validate_should_raise_when_payload_is_invalid(payload):
    with pytest.raises(ValidationError):
        Event.model_validate(payload)
