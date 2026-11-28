import logging
import random
import time
import uuid

import httpx

logger = logging.getLogger(__name__)


def send_event(client: httpx.Client, url: str, event: dict, idempotency_key: str) -> None:
    try:
        client.post(url, json=event, headers={"Idempotency-Key": idempotency_key}).raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Failed to send %s: %s", event, error)
    else:
        logger.info("Sent %s", event)


def run(client: httpx.Client, url: str, events: list[dict], interval: float) -> None:
    next_send = time.monotonic()
    while True:
        send_event(client, url, random.choice(events), str(uuid.uuid4()))
        # Schedule from the previous send, not from now, so request time does not stretch the period.
        # If a send overran the interval, start counting from now instead of sending in a burst.
        next_send = max(next_send + interval, time.monotonic())
        time.sleep(max(0, next_send - time.monotonic()))
