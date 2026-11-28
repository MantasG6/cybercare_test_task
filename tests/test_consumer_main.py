from consumer.__main__ import build_limiter, read_max_in_flight


def test_build_limiter_should_use_defaults_when_rate_limit_table_is_missing():
    limiter = build_limiter({})

    assert (limiter.rate, limiter.capacity) == (10, 20)


def test_build_limiter_should_use_configured_values_when_rate_limit_table_is_present():
    limiter = build_limiter({"rate_limit": {"requests_per_second": 2, "burst": 5}})

    assert (limiter.rate, limiter.capacity) == (2, 5)


def test_read_max_in_flight_should_return_40_when_concurrency_table_is_missing():
    assert read_max_in_flight({}) == 40


def test_read_max_in_flight_should_return_configured_value_when_concurrency_table_is_present():
    assert read_max_in_flight({"concurrency": {"max_in_flight": 5}}) == 5
