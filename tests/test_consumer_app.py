from fastapi.testclient import TestClient

from consumer.app import create_app


def test_post_event_should_store_event_when_event_is_valid(collection):
    client = TestClient(create_app(collection))

    response = client.post("/event", json={"event_type": "message", "event_payload": "hello"})

    assert response.status_code == 201
    assert collection.find_one({}, {"_id": False, "received_at": False}) == {
        "event_type": "message",
        "event_payload": "hello",
    }


def test_post_event_should_return_422_and_not_store_when_event_is_invalid(collection):
    client = TestClient(create_app(collection))

    response = client.post("/event", json={"event_type": 123, "event_payload": {}})

    assert response.status_code == 422
    assert collection.count_documents({}) == 0


def test_post_event_should_store_once_and_return_201_when_idempotency_key_repeats(collection):
    client = TestClient(create_app(collection))
    event = {"event_type": "message", "event_payload": "hello"}

    responses = [client.post("/event", json=event, headers={"Idempotency-Key": "key-1"}) for _ in range(2)]

    assert [response.status_code for response in responses] == [201, 201]
    assert collection.count_documents({}) == 1
    assert collection.find_one({}, {"_id": False, "received_at": False}) == {**event, "idempotency_key": "key-1"}


def test_post_event_should_store_each_without_key_field_when_idempotency_key_is_missing(collection):
    client = TestClient(create_app(collection))
    event = {"event_type": "message", "event_payload": "hello"}

    responses = [client.post("/event", json=event) for _ in range(2)]

    assert [response.status_code for response in responses] == [201, 201]
    assert collection.count_documents({}) == 2
    assert collection.count_documents({"idempotency_key": {"$exists": True}}) == 0
