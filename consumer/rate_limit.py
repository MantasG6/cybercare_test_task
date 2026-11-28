import threading
import time
from collections.abc import Callable


class TokenBucket:
    def __init__(self, rate: float, capacity: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Take one token. Return 0 on success, otherwise the seconds until the next token."""
        with self._lock:
            now = self._clock()
            self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return 0.0
            return (1 - self._tokens) / self.rate

    def release(self) -> None:
        """Give back a token taken by a request that was turned away for another reason."""
        with self._lock:
            self._tokens = min(self.capacity, self._tokens + 1)
