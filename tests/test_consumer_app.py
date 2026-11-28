import threading
from contextlib import contextmanager

import anyio.to_thread
import pytest
from fastapi.testclient import TestClient

from consumer.app import create_app
from consumer.rate_limit import TokenBucket
from consumer.store import save_event

VALID_EVENT = {"event_type": "message", "event_payload": "hello"}
INVALID_EVENT = {"event_type": 123, "event_payload": {}}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def client_for(collection, rate=10, burst=20, clock=None, max_in_flight=40):
    return TestClient(create_app(collection, TokenBucket(rate, burst, clock or FakeClock()), max_in_flight))


def post_concurrently(client, count):
    barrier = threading.Barrier(count)
    statuses = []

    def post():
        barrier.wait()
        statuses.append(client.post("/event", json=VALID_EVENT).status_code)

    threads = [threading.Thread(target=post) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return statuses


@contextmanager
def held_in_store(monkeypatch, client, count):
    """Keep `count` POST /event requests blocked inside the store until the block exits; yields their statuses."""
    entered = threading.Semaphore(0)
    release = threading.Event()
    statuses = []

    def blocking_save(*args):
        entered.release()
        release.wait()
        save_event(*args)

    def post():
        statuses.append(client.post("/event", json=VALID_EVENT).status_code)

    monkeypatch.setattr("consumer.app.save_event", blocking_save)
    threads = [threading.Thread(target=post) for _ in range(count)]
    for thread in threads:
        thread.start()
    try:
        for _ in range(count):
            assert entered.acquire(timeout=5)
        yield statuses
    finally:
        release.set()
        for thread in threads:
            thread.join()


def test_post_event_should_store_event_when_event_is_valid(collection):
    client = client_for(collection)

    response = client.post("/event", json=VALID_EVENT)

    assert response.status_code == 201
    assert collection.find_one({}, {"_id": False, "received_at": False}) == VALID_EVENT


def test_post_event_should_return_422_and_not_store_when_event_is_invalid(collection):
    client = client_for(collection)

    response = client.post("/event", json=INVALID_EVENT)

    assert response.status_code == 422
    assert collection.count_documents({}) == 0


def test_post_event_should_return_429_and_not_store_when_burst_exceeded(collection):
    client = client_for(collection, rate=10, burst=3)
    for _ in range(3):
        assert client.post("/event", json=VALID_EVENT).status_code == 201

    response = client.post("/event", json=VALID_EVENT)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert collection.count_documents({}) == 3


def test_post_event_should_round_up_retry_after_when_next_token_is_seconds_away(collection):
    client = client_for(collection, rate=0.4, burst=1)
    client.post("/event", json=VALID_EVENT)

    response = client.post("/event", json=VALID_EVENT)

    assert response.headers["Retry-After"] == "3"


def test_post_event_should_accept_again_when_enough_time_has_passed(collection):
    clock = FakeClock()
    client = client_for(collection, rate=10, burst=1, clock=clock)
    client.post("/event", json=VALID_EVENT)
    assert client.post("/event", json=VALID_EVENT).status_code == 429

    clock.now = 0.1

    assert client.post("/event", json=VALID_EVENT).status_code == 201


def test_post_event_should_count_invalid_requests_when_limiting(collection):
    client = client_for(collection, rate=10, burst=2)
    for _ in range(2):
        assert client.post("/event", json=INVALID_EVENT).status_code == 422

    response = client.post("/event", json=VALID_EVENT)

    assert response.status_code == 429
    assert collection.count_documents({}) == 0


def test_post_event_should_accept_all_when_concurrent_requests_within_burst(collection):
    client = client_for(collection, rate=10, burst=10)

    statuses = post_concurrently(client, 10)

    assert statuses == [201] * 10


def test_post_event_should_reject_exactly_one_when_concurrent_requests_exceed_burst_by_one(collection):
    client = client_for(collection, rate=10, burst=10)

    statuses = post_concurrently(client, 11)

    assert sorted(statuses) == [201] * 10 + [429]
    assert collection.count_documents({}) == 10


def test_post_event_should_store_once_and_return_201_when_idempotency_key_repeats(collection):
    client = client_for(collection)
    event = {"event_type": "message", "event_payload": "hello"}

    responses = [client.post("/event", json=event, headers={"Idempotency-Key": "key-1"}) for _ in range(2)]

    assert [response.status_code for response in responses] == [201, 201]
    assert collection.count_documents({}) == 1
    assert collection.find_one({}, {"_id": False, "received_at": False}) == {**event, "idempotency_key": "key-1"}


def test_post_event_should_store_each_without_key_field_when_idempotency_key_is_missing(collection):
    client = client_for(collection)
    event = {"event_type": "message", "event_payload": "hello"}

    responses = [client.post("/event", json=event) for _ in range(2)]

    assert [response.status_code for response in responses] == [201, 201]
    assert collection.count_documents({}) == 2
    assert collection.count_documents({"idempotency_key": {"$exists": True}}) == 0


def test_post_event_should_store_each_without_key_field_when_idempotency_key_is_blank(collection):
    client = client_for(collection)
    event = {"event_type": "message", "event_payload": "hello"}

    responses = [client.post("/event", json=event, headers={"Idempotency-Key": ""}) for _ in range(2)]

    assert [response.status_code for response in responses] == [201, 201]
    assert collection.count_documents({}) == 2
    assert collection.count_documents({"idempotency_key": {"$exists": True}}) == 0


def test_post_event_should_return_503_and_not_store_when_max_in_flight_requests_are_in_progress(collection, monkeypatch):
    with client_for(collection, max_in_flight=2) as client:
        with held_in_store(monkeypatch, client, 2) as held_statuses:
            response = client.post("/event", json=VALID_EVENT)

        assert response.status_code == 503
        assert "Retry-After" not in response.headers
        assert held_statuses == [201, 201]
        assert collection.count_documents({}) == 2
        assert client.post("/event", json=VALID_EVENT).status_code == 201


def test_post_event_should_free_in_flight_slots_when_requests_are_invalid_or_valid(collection, monkeypatch):
    with client_for(collection, max_in_flight=2) as client:
        assert client.post("/event", json=INVALID_EVENT).status_code == 422
        assert client.post("/event", json=VALID_EVENT).status_code == 201

        with held_in_store(monkeypatch, client, 2) as held_statuses:
            pass

        assert held_statuses == [201, 201]


def test_post_event_should_return_422_when_event_is_invalid_and_max_in_flight_requests_are_in_progress(collection, monkeypatch):
    with client_for(collection, max_in_flight=1) as client:
        with held_in_store(monkeypatch, client, 1):
            response = client.post("/event", json=INVALID_EVENT)

        assert response.status_code == 422


def test_post_event_should_free_in_flight_slot_when_store_raises(collection, monkeypatch):
    def failing_save(*args):
        raise RuntimeError("store failed")

    with client_for(collection, max_in_flight=1) as client:
        monkeypatch.setattr("consumer.app.save_event", failing_save)
        with pytest.raises(RuntimeError):
            client.post("/event", json=VALID_EVENT)

        with held_in_store(monkeypatch, client, 1) as held_statuses:
            pass

        assert held_statuses == [201]


def test_post_event_should_return_429_without_taking_in_flight_slot_when_both_limits_are_exceeded(collection, monkeypatch):
    clock = FakeClock()
    with client_for(collection, rate=10, burst=1, clock=clock, max_in_flight=1) as client:
        with held_in_store(monkeypatch, client, 1):
            response = client.post("/event", json=VALID_EVENT)

        assert response.status_code == 429
        clock.now = 0.1
        assert client.post("/event", json=VALID_EVENT).status_code == 201


def test_create_app_should_size_default_thread_limiter_to_max_in_flight_when_app_starts(collection):
    async def total_tokens():
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    with client_for(collection, max_in_flight=5) as client:
        assert client.portal.call(total_tokens) == 5
