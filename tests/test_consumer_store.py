from datetime import datetime

from consumer.models import Event
from consumer.store import save_event


def test_save_event_should_add_received_at_when_storing_event(collection):
    save_event(collection, Event(event_type="message", event_payload="hello"))

    stored = collection.find_one({}, {"_id": False})
    assert isinstance(stored.pop("received_at"), datetime)
    assert stored == {"event_type": "message", "event_payload": "hello"}
