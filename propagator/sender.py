import logging
import random
import time

import httpx

logger = logging.getLogger(__name__)


def send_event(client: httpx.Client, url: str, event: dict) -> None:
    try:
        client.post(url, json=event).raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Failed to send %s: %s", event, error)
    else:
        logger.info("Sent %s", event)


def run(client: httpx.Client, url: str, events: list[dict], interval: float) -> None:
    while True:
        send_event(client, url, random.choice(events))
        time.sleep(interval)
