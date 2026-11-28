import logging
import queue
import threading
from collections.abc import Callable

from consumer.models import Event

logger = logging.getLogger(__name__)

Store = Callable[[Event, str | None], None]


class EventQueue:
    """A bounded in-memory queue of events, written by background worker threads."""

    def __init__(self, store: Store, max_size: int, workers: int) -> None:
        if max_size < 1 or workers < 1:
            raise ValueError("max_size and workers must be at least 1")
        self.max_size = max_size
        self.workers = workers
        self._store = store
        self._queue: queue.Queue[tuple[Event, str | None] | None] = queue.Queue(max_size)
        self._threads: list[threading.Thread] = []

    def put(self, event: Event, idempotency_key: str | None) -> bool:
        """Queue an event. Return False, without queuing it, if the queue is full."""
        try:
            self._queue.put_nowait((event, idempotency_key))
        except queue.Full:
            return False
        return True

    def start(self) -> None:
        self._threads = [threading.Thread(target=self._work, daemon=True) for _ in range(self.workers)]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        """Write every queued event, then stop the workers."""
        # One stop marker per worker, queued after the events, so every event is written first.
        for _ in self._threads:
            self._queue.put(None)
        for thread in self._threads:
            thread.join()

    def _work(self) -> None:
        while (item := self._queue.get()) is not None:
            try:
                self._store(*item)
            except Exception:
                logger.exception("Failed to store %s", item[0])
