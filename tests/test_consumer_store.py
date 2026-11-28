from datetime import datetime

from consumer.models import Event
from consumer.store import create_indexes, save_event


def test_save_event_should_add_received_at_when_storing_event(collection):
    save_event(collection, Event(event_type="message", event_payload="hello"))

    stored = collection.find_one({}, {"_id": False})
    assert isinstance(stored.pop("received_at"), datetime)
    assert stored == {"event_type": "message", "event_payload": "hello"}


def test_save_event_should_store_once_when_idempotency_key_repeats(collection):
    create_indexes(collection)
    event = Event(event_type="message", event_payload="hello")

    save_event(collection, event, "key-1")
    save_event(collection, event, "key-1")

    assert collection.count_documents({"idempotency_key": "key-1"}) == 1


def test_save_event_should_store_each_when_idempotency_key_is_missing(collection):
    create_indexes(collection)
    event = Event(event_type="message", event_payload="hello")

    save_event(collection, event)
    save_event(collection, event)

    assert collection.count_documents({"idempotency_key": {"$exists": False}}) == 2
