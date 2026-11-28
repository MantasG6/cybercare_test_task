import threading
import time
from functools import partial

from fastapi.testclient import TestClient

from consumer.app import create_app
from consumer.event_queue import EventQueue
from consumer.rate_limit import TokenBucket
from consumer.store import save_event

VALID_EVENT = {"event_type": "message", "event_payload": "hello"}
INVALID_EVENT = {"event_type": 123, "event_payload": {}}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class BlockingStore:
    """Saves events, but only once released, so the queue can be filled."""

    def __init__(self, collection):
        self.collection = collection
        self.entered = threading.Event()
        self.released = threading.Event()

    def __call__(self, event, idempotency_key):
        self.entered.set()
        self.released.wait(5)  # A timeout, so a failing test cannot hang on shutdown.
        save_event(self.collection, event, idempotency_key)


def client_for(collection, rate=10, burst=20, clock=None, max_size=20, store=None):
    events = EventQueue(store or partial(save_event, collection), max_size, workers=1)
    return TestClient(create_app(collection, TokenBucket(rate, burst, clock or FakeClock()), events))


def wait_for_documents(collection, count, timeout=5):
    deadline = time.monotonic() + timeout
    while collection.count_documents({}) < count:
        assert time.monotonic() < deadline, f"fewer than {count} documents after {timeout} s"
        time.sleep(0.01)


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


def test_post_event_should_return_202_and_store_event_when_event_is_valid(collection):
    with client_for(collection) as client:
        response = client.post("/event", json=VALID_EVENT)

        assert response.status_code == 202
        wait_for_documents(collection, 1)
        assert collection.find_one({}, {"_id": False, "received_at": False}) == VALID_EVENT


def test_post_event_should_return_503_and_not_queue_when_queue_is_full(collection):
    store = BlockingStore(collection)
    with client_for(collection, max_size=2, store=store) as client:
        assert client.post("/event", json=VALID_EVENT).status_code == 202
        store.entered.wait(5)  # The worker holds the first event, so the queue is empty again.
        assert [client.post("/event", json=VALID_EVENT).status_code for _ in range(2)] == [202, 202]

        response = client.post("/event", json=VALID_EVENT)

        store.released.set()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert collection.count_documents({}) == 3


def test_shutdown_should_store_every_queued_event_when_workers_were_blocked(collection):
    store = BlockingStore(collection)
    with client_for(collection, max_size=5, store=store) as client:
        assert [client.post("/event", json=VALID_EVENT).status_code for _ in range(5)] == [202] * 5

        store.released.set()

    assert collection.count_documents({}) == 5


def test_post_event_should_return_422_and_not_store_when_event_is_invalid(collection):
    with client_for(collection) as client:
        response = client.post("/event", json=INVALID_EVENT)

    assert response.status_code == 422
    assert collection.count_documents({}) == 0


def test_post_event_should_return_429_and_not_store_when_burst_exceeded(collection):
    with client_for(collection, rate=10, burst=3) as client:
        for _ in range(3):
            assert client.post("/event", json=VALID_EVENT).status_code == 202

        response = client.post("/event", json=VALID_EVENT)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert collection.count_documents({}) == 3


def test_post_event_should_round_up_retry_after_when_next_token_is_seconds_away(collection):
    with client_for(collection, rate=0.4, burst=1) as client:
        client.post("/event", json=VALID_EVENT)

        response = client.post("/event", json=VALID_EVENT)

    assert response.headers["Retry-After"] == "3"


def test_post_event_should_accept_again_when_enough_time_has_passed(collection):
    clock = FakeClock()
    with client_for(collection, rate=10, burst=1, clock=clock) as client:
        client.post("/event", json=VALID_EVENT)
        assert client.post("/event", json=VALID_EVENT).status_code == 429

        clock.now = 0.1

        assert client.post("/event", json=VALID_EVENT).status_code == 202


def test_post_event_should_count_invalid_requests_when_limiting(collection):
    with client_for(collection, rate=10, burst=2) as client:
        for _ in range(2):
            assert client.post("/event", json=INVALID_EVENT).status_code == 422

        response = client.post("/event", json=VALID_EVENT)

    assert response.status_code == 429
    assert collection.count_documents({}) == 0


def test_post_event_should_check_rate_limit_before_queue_when_both_are_exceeded(collection):
    store = BlockingStore(collection)
    with client_for(collection, rate=10, burst=2, max_size=1, store=store) as client:
        assert client.post("/event", json=VALID_EVENT).status_code == 202
        store.entered.wait(5)
        assert client.post("/event", json=VALID_EVENT).status_code == 202  # Fills the queue.

        response = client.post("/event", json=VALID_EVENT)

        store.released.set()
    assert response.status_code == 429
    assert collection.count_documents({}) == 2


def test_post_event_should_accept_all_when_concurrent_requests_within_burst(collection):
    with client_for(collection, rate=10, burst=10) as client:
        statuses = post_concurrently(client, 10)

    assert statuses == [202] * 10


def test_post_event_should_reject_exactly_one_when_concurrent_requests_exceed_burst_by_one(collection):
    with client_for(collection, rate=10, burst=10) as client:
        statuses = post_concurrently(client, 11)

    assert sorted(statuses) == [202] * 10 + [429]
    assert collection.count_documents({}) == 10


def test_post_event_should_store_once_and_return_202_when_idempotency_key_repeats(collection):
    event = {"event_type": "message", "event_payload": "hello"}
    with client_for(collection) as client:
        responses = [client.post("/event", json=event, headers={"Idempotency-Key": "key-1"}) for _ in range(2)]

    assert [response.status_code for response in responses] == [202, 202]
    assert collection.count_documents({}) == 1
    assert collection.find_one({}, {"_id": False, "received_at": False}) == {**event, "idempotency_key": "key-1"}


def test_post_event_should_store_each_without_key_field_when_idempotency_key_is_missing(collection):
    event = {"event_type": "message", "event_payload": "hello"}
    with client_for(collection) as client:
        responses = [client.post("/event", json=event) for _ in range(2)]

    assert [response.status_code for response in responses] == [202, 202]
    assert collection.count_documents({}) == 2
    assert collection.count_documents({"idempotency_key": {"$exists": True}}) == 0


def test_post_event_should_store_each_without_key_field_when_idempotency_key_is_blank(collection):
    event = {"event_type": "message", "event_payload": "hello"}
    with client_for(collection) as client:
        responses = [client.post("/event", json=event, headers={"Idempotency-Key": ""}) for _ in range(2)]

    assert [response.status_code for response in responses] == [202, 202]
    assert collection.count_documents({}) == 2
    assert collection.count_documents({"idempotency_key": {"$exists": True}}) == 0
