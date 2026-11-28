import logging

import pytest

from consumer.event_queue import EventQueue
from consumer.models import Event


def event(payload):
    return Event(event_type="message", event_payload=payload)


def test_put_should_return_false_and_not_queue_when_queue_is_full():
    stored = []
    events = EventQueue(lambda event, key: stored.append(event), max_size=2, workers=1)
    assert events.put(event("1"), None) and events.put(event("2"), None)

    accepted = events.put(event("3"), None)

    events.start()
    events.stop()
    assert not accepted
    assert stored == [event("1"), event("2")]


def test_stop_should_store_every_queued_event_in_order_when_workers_start_late():
    stored = []
    events = EventQueue(lambda event, key: stored.append((event, key)), max_size=5, workers=1)
    for i in range(5):
        events.put(event(str(i)), f"key-{i}")

    events.start()
    events.stop()

    assert stored == [(event(str(i)), f"key-{i}") for i in range(5)]


def test_stop_should_store_every_queued_event_when_there_are_several_workers():
    stored = []
    events = EventQueue(lambda event, key: stored.append(event), max_size=10, workers=3)
    events.start()
    for i in range(10):
        events.put(event(str(i)), None)

    events.stop()

    assert sorted(e.event_payload for e in stored) == [str(i) for i in range(10)]


def test_work_should_log_and_keep_going_when_store_raises(caplog):
    stored = []

    def store(event, key):
        if event.event_payload == "bad":
            raise RuntimeError("boom")
        stored.append(event)

    events = EventQueue(store, max_size=3, workers=1)
    for payload in ["1", "bad", "2"]:
        events.put(event(payload), None)

    with caplog.at_level(logging.ERROR):
        events.start()
        events.stop()

    assert stored == [event("1"), event("2")]
    assert "boom" in caplog.text


@pytest.mark.parametrize("max_size, workers", [(0, 1), (1, 0)])
def test_init_should_raise_when_max_size_or_workers_is_below_one(max_size, workers):
    with pytest.raises(ValueError):
        EventQueue(lambda event, key: None, max_size=max_size, workers=workers)
