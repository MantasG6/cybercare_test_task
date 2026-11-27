from fastapi.testclient import TestClient

from consumer.app import create_app


def test_valid_event_is_stored(collection):
    client = TestClient(create_app(collection))

    response = client.post("/event", json={"event_type": "message", "event_payload": "hello"})

    assert response.status_code == 201
    assert collection.find_one({}, {"_id": False, "received_at": False}) == {
        "event_type": "message",
        "event_payload": "hello",
    }


def test_invalid_event_is_rejected_and_not_stored(collection):
    client = TestClient(create_app(collection))

    response = client.post("/event", json={"event_type": 123, "event_payload": {}})

    assert response.status_code == 422
    assert collection.count_documents({}) == 0
