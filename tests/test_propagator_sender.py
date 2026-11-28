import json
import uuid

import httpx
import pytest

from propagator import sender
from propagator.sender import run, send_event

URL = "http://consumer/event"
KEY = "test-key"
EVENTS = [
    {"event_type": "message", "event_payload": "hello"},
    {"event_type": "user_joined", "event_payload": "Peter"},
]


class StopLoop(Exception):
    pass


def client_responding(responses, sent):
    responses = iter(responses)

    def handler(request):
        sent.append(request)
        return next(responses)

    return httpx.Client(transport=httpx.MockTransport(handler))


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
        run(client_returning(201, sent), URL, EVENTS, 5, 30)

    assert [str(request.url) for request in sent] == [URL] * 3
    assert all(json.loads(request.content) in EVENTS for request in sent)
    assert clock.sleeps == [5, 5, 5]


def slow_client(clock, seconds):
    def handler(request):
        clock.now += seconds
        return httpx.Response(202)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_run_should_shorten_wait_when_request_takes_time(clock):
    with pytest.raises(StopLoop):
        run(slow_client(clock, 2), URL, EVENTS, 5, 30)

    assert clock.sleeps == [3, 3, 3]


def test_run_should_send_immediately_when_request_overruns_interval(clock):
    with pytest.raises(StopLoop):
        run(slow_client(clock, 7), URL, EVENTS, 5, 30)

    assert clock.sleeps == [0, 0, 0]


def test_run_should_send_new_uuid4_idempotency_key_when_sending_each_event(clock):
    sent = []
    client = client_returning(202, sent)

    with pytest.raises(StopLoop):
        run(client_returning(201, sent), URL, EVENTS, 5, 30)

    keys = [request.headers["Idempotency-Key"] for request in sent]
    assert all(uuid.UUID(key).version == 4 for key in keys)
    assert len(set(keys)) == 3


def test_send_event_should_not_raise_when_response_is_error_status():
    send_event(client_returning(422, []), URL, EVENTS[0], KEY)


def test_send_event_should_not_raise_when_connection_fails():
    def handler(request):
        raise httpx.ConnectError("refused")

    send_event(httpx.Client(transport=httpx.MockTransport(handler)), URL, EVENTS[0], KEY)


def test_run_should_resend_same_event_with_same_key_after_capped_retry_after_when_rejected(clock):
    sent = []
    responses = [
        httpx.Response(429, headers={"Retry-After": "3"}),
        httpx.Response(503, headers={"Retry-After": "60"}),
        httpx.Response(202),
    ]

    with pytest.raises(StopLoop):
        run(client_responding(responses, sent), URL, EVENTS, 5, 30)

    assert clock.sleeps == [3, 30, 5]
    assert len({request.content for request in sent}) == 1
    assert len({request.headers["Idempotency-Key"] for request in sent}) == 1


def test_run_should_double_wait_up_to_cap_when_rejected_without_usable_retry_after(clock):
    clock.stop_after = 4
    responses = [
        httpx.Response(429),
        httpx.Response(503, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        httpx.Response(429),
        httpx.Response(503),
    ]

    with pytest.raises(StopLoop):
        run(client_responding(responses, []), URL, EVENTS, 5, 30)

    assert clock.sleeps == [10, 20, 30, 30]


def test_run_should_return_to_interval_with_new_event_and_key_when_resend_succeeds(clock, monkeypatch):
    clock.stop_after = 4
    chosen = iter(EVENTS)
    monkeypatch.setattr(sender.random, "choice", lambda events: next(chosen))
    sent = []
    responses = [httpx.Response(429), httpx.Response(429), httpx.Response(202), httpx.Response(202)]

    with pytest.raises(StopLoop):
        run(client_responding(responses, sent), URL, EVENTS, 5, 30)

    assert clock.sleeps == [10, 20, 5, 5]
    assert [json.loads(request.content) for request in sent] == [EVENTS[0]] * 3 + [EVENTS[1]]
    keys = [request.headers["Idempotency-Key"] for request in sent]
    assert keys[0] == keys[1] == keys[2] != keys[3]


@pytest.mark.parametrize("status_code", [422, 500])
def test_run_should_move_on_to_new_key_after_interval_when_send_fails_without_backoff_status(clock, status_code):
    sent = []

    with pytest.raises(StopLoop):
        run(client_returning(status_code, sent), URL, EVENTS, 5, 30)

    assert clock.sleeps == [5, 5, 5]
    assert len({request.headers["Idempotency-Key"] for request in sent}) == 3


def test_run_should_move_on_after_interval_when_connection_fails(clock):
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(StopLoop):
        run(httpx.Client(transport=httpx.MockTransport(handler)), URL, EVENTS, 5, 30)

    assert clock.sleeps == [5, 5, 5]
