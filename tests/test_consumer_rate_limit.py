import pytest

from consumer.rate_limit import TokenBucket


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_acquire_should_succeed_when_within_capacity():
    bucket = TokenBucket(rate=1, capacity=3, clock=FakeClock())

    assert [bucket.acquire() for _ in range(3)] == [0, 0, 0]


def test_acquire_should_return_seconds_until_next_token_when_empty():
    bucket = TokenBucket(rate=4, capacity=1, clock=FakeClock())
    bucket.acquire()

    assert bucket.acquire() == pytest.approx(0.25)


def test_acquire_should_succeed_again_when_tokens_refilled():
    clock = FakeClock()
    bucket = TokenBucket(rate=2, capacity=1, clock=clock)
    bucket.acquire()

    clock.now = 0.5

    assert bucket.acquire() == 0


def test_acquire_should_not_exceed_capacity_when_idle_for_long():
    clock = FakeClock()
    bucket = TokenBucket(rate=1, capacity=2, clock=clock)

    clock.now = 100
    results = [bucket.acquire() for _ in range(3)]

    assert results[:2] == [0, 0]
    assert results[2] > 0


def test_release_should_return_token_when_one_was_taken():
    bucket = TokenBucket(rate=1, capacity=1, clock=FakeClock())
    bucket.acquire()

    bucket.release()

    assert bucket.acquire() == 0


def test_release_should_not_exceed_capacity_when_bucket_is_full():
    bucket = TokenBucket(rate=1, capacity=1, clock=FakeClock())

    bucket.release()

    assert [bucket.acquire() == 0 for _ in range(2)] == [True, False]
