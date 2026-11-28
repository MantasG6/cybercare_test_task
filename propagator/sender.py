import logging
import random
import time
import uuid

import httpx

logger = logging.getLogger(__name__)

BACKOFF_STATUSES = {429, 503}


def send_event(client: httpx.Client, url: str, event: dict, idempotency_key: str) -> httpx.Response | None:
    """Send one event. Return the response, or None if no response came back."""
    try:
        response = client.post(url, json=event, headers={"Idempotency-Key": idempotency_key})
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        logger.warning("Failed to send %s: %s", event, error)
        return error.response
    except httpx.HTTPError as error:
        logger.warning("Failed to send %s: %s", event, error)
        return None
    logger.info("Sent %s", event)
    return response


def backoff_seconds(response: httpx.Response | None, interval: float, rejections: int, max_backoff: float) -> float:
    retry_after = response.headers.get("Retry-After", "") if response is not None else ""
    if retry_after.isascii() and retry_after.isdigit():
        seconds, reason = int(retry_after), "Retry-After"
    else:
        seconds, reason = interval * 2**rejections, f"rejection {rejections} in a row"
    seconds = min(seconds, max_backoff)
    cause = response.status_code if response is not None else "no response"
    logger.info("Backing off %s s after %s (%s)", seconds, cause, reason)
    return seconds


def run(client: httpx.Client, url: str, events: list[dict], interval: float, max_backoff: float) -> None:
    next_send = time.monotonic()
    rejections = 0
    while True:
        if rejections == 0:
            event, key = random.choice(events), str(uuid.uuid4())
        response = send_event(client, url, event, key)
        if response is None or response.status_code in BACKOFF_STATUSES:
            # Resend the same event with the same key. The backoff replaces the normal wait.
            # With no response the event may or may not be stored; the key keeps the resend from storing it twice.
            rejections += 1
            time.sleep(backoff_seconds(response, interval, rejections, max_backoff))
            next_send = time.monotonic()
            continue
        rejections = 0
        # Schedule from the previous send, not from now, so request time does not stretch the period.
        # If a send overran the interval, start counting from now instead of sending in a burst.
        next_send = max(next_send + interval, time.monotonic())
        time.sleep(max(0, next_send - time.monotonic()))
