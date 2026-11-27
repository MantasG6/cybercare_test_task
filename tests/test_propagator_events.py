from propagator.events import load_events


def test_load_events_reads_array_from_file(tmp_path):
    path = tmp_path / "events.json"
    path.write_text('[{"event_type": "message", "event_payload": "hello"}]')

    assert load_events(path) == [{"event_type": "message", "event_payload": "hello"}]


def test_bundled_events_file_has_task_events():
    events = load_events("data/events.json")

    assert len(events) == 11
    assert {"event_type": 123, "event_payload": {}} in events
