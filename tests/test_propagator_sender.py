import json

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


def stop_after(count, sleeps):
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == count:
            raise StopLoop

    return sleep


def test_run_posts_random_events_from_list_every_interval(monkeypatch):
    sent, sleeps = [], []
    monkeypatch.setattr(sender.time, "sleep", stop_after(3, sleeps))

    with pytest.raises(StopLoop):
        run(client_returning(201, sent), URL, EVENTS, 5)

    assert [str(request.url) for request in sent] == [URL] * 3
    assert all(json.loads(request.content) in EVENTS for request in sent)
    assert sleeps == [5, 5, 5]


def test_send_event_does_not_raise_on_error_status():
    send_event(client_returning(422, []), URL, EVENTS[0])


def test_send_event_does_not_raise_on_connection_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    send_event(httpx.Client(transport=httpx.MockTransport(handler)), URL, EVENTS[0])
