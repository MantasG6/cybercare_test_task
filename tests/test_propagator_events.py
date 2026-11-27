from pathlib import Path

import pytest

from propagator.events import load_events

EVENTS_FILE = Path(__file__).parent.parent / "data" / "events.json"


def test_load_events_should_return_events_when_file_has_array(tmp_path):
    path = tmp_path / "events.json"
    path.write_text('[{"event_type": "message", "event_payload": "hello"}]')

    assert load_events(path) == [{"event_type": "message", "event_payload": "hello"}]


def test_load_events_should_return_task_events_when_reading_bundled_file():
    events = load_events(EVENTS_FILE)

    assert len(events) == 11
    assert {"event_type": 123, "event_payload": {}} in events


@pytest.mark.parametrize("content", ["[]", '{"event_type": "message", "event_payload": "hello"}'])
def test_load_events_should_raise_when_file_is_empty_or_not_list(tmp_path, content):
    path = tmp_path / "events.json"
    path.write_text(content)

    with pytest.raises(ValueError, match="non-empty JSON array"):
        load_events(path)
