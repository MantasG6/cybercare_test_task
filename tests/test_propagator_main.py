import sys

from propagator import __main__ as propagator_main


def test_main_should_use_30_second_max_backoff_when_config_has_no_max_backoff_seconds(tmp_path, monkeypatch):
    config = tmp_path / "propagator.toml"
    config.write_text('interval_seconds = 5\nendpoint_url = "http://consumer/event"\nevents_file = "events.json"\n')
    calls = []
    monkeypatch.setattr(sys, "argv", ["propagator", "--config", str(config)])
    monkeypatch.setattr(propagator_main, "load_events", lambda path: [])
    monkeypatch.setattr(propagator_main, "run", lambda *args: calls.append(args))

    propagator_main.main()

    assert calls[0][4] == 30
