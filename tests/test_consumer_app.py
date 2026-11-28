import threading

from fastapi.testclient import TestClient

from consumer.app import create_app
from consumer.rate_limit import TokenBucket

VALID_EVENT = {"event_type": "message", "event_payload": "hello"}
INVALID_EVENT = {"event_type": 123, "event_payload": {}}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def client_for(collection, rate=10, burst=20, clock=None):
    return TestClient(create_app(collection, TokenBucket(rate, burst, clock or FakeClock())))


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


def test_post_event_should_round_retry_after_up_when_next_token_is_seconds_away(collection):
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
