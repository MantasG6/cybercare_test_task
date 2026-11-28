from consumer.__main__ import build_event_queue, build_limiter


def test_build_limiter_should_use_defaults_when_rate_limit_table_is_missing():
    limiter = build_limiter({})

    assert (limiter.rate, limiter.capacity) == (10, 20)


def test_build_limiter_should_use_configured_values_when_rate_limit_table_is_present():
    limiter = build_limiter({"rate_limit": {"requests_per_second": 2, "burst": 5}})

    assert (limiter.rate, limiter.capacity) == (2, 5)


def test_build_event_queue_should_use_defaults_when_queue_table_is_missing():
    events = build_event_queue({}, lambda event, key: None)

    assert (events.max_size, events.workers) == (20, 1)


def test_build_event_queue_should_use_configured_values_when_queue_table_is_present():
    events = build_event_queue({"queue": {"max_size": 5, "workers": 3}}, lambda event, key: None)

    assert (events.max_size, events.workers) == (5, 3)
