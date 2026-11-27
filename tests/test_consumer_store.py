from datetime import datetime

from consumer.models import Event
from consumer.store import save_event


def test_save_event_stores_event_with_received_at(collection):
    save_event(collection, Event(event_type="message", event_payload="hello"))

    stored = collection.find_one({}, {"_id": False})
    assert isinstance(stored.pop("received_at"), datetime)
    assert stored == {"event_type": "message", "event_payload": "hello"}
