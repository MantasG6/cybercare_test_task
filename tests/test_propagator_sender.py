import json
import uuid

import httpx
import pytest

from propagator import sender
from propagator.sender import run, send_event

URL = "http://consumer/event"
EVENTS = [
    {"event_type": "message", "event_payload": "hello"},
    {"event_type": "user_joined", "event_payload": "Peter"},
]


class StopLoop(Exception):
    pass


def client_returning(status_code, sent):
    def handler(request):
        sent.append(request)
        return httpx.Response(status_code)

    return httpx.Client(transport=httpx.MockTransport(handler))


class FakeClock:
    def __init__(self, stop_after):
        self.now = 0.0
        self.sleeps = []
        self.stop_after = stop_after

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
        if len(self.sleeps) == self.stop_after:
            raise StopLoop


@pytest.fixture
def clock(monkeypatch):
    clock = FakeClock(stop_after=3)
    monkeypatch.setattr(sender.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(sender.time, "sleep", clock.sleep)
    return clock


def test_run_should_post_random_event_from_list_when_interval_elapses(clock):
    sent = []

    with pytest.raises(StopLoop):
        run(client_returning(201, sent), URL, EVENTS, 5)

    assert [str(request.url) for request in sent] == [URL] * 3
    assert all(json.loads(request.content) in EVENTS for request in sent)
    assert clock.sleeps == [5, 5, 5]


def slow_client(clock, seconds):
    def handler(request):
        clock.now += seconds
        return httpx.Response(201)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_run_should_shorten_wait_when_request_takes_time(clock):
    with pytest.raises(StopLoop):
        run(slow_client(clock, 2), URL, EVENTS, 5)

    assert clock.sleeps == [3, 3, 3]


def test_run_should_send_immediately_when_request_overruns_interval(clock):
    with pytest.raises(StopLoop):
        run(slow_client(clock, 7), URL, EVENTS, 5)

    assert clock.sleeps == [0, 0, 0]


def test_send_event_should_send_new_uuid4_idempotency_key_when_sending_each_event():
    sent = []
    client = client_returning(201, sent)

    send_event(client, URL, EVENTS[0])
    send_event(client, URL, EVENTS[0])

    keys = [request.headers["Idempotency-Key"] for request in sent]
    assert all(uuid.UUID(key).version == 4 for key in keys)
    assert keys[0] != keys[1]


def test_send_event_should_not_raise_when_response_is_error_status():
    send_event(client_returning(422, []), URL, EVENTS[0])


def test_send_event_should_not_raise_when_connection_fails():
    def handler(request):
        raise httpx.ConnectError("refused")

    send_event(httpx.Client(transport=httpx.MockTransport(handler)), URL, EVENTS[0])
