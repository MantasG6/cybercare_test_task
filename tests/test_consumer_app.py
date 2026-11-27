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
