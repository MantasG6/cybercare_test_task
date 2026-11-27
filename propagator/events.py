import json
from pathlib import Path


def load_events(path: str | Path) -> list[dict]:
    with open(path) as f:
        events = json.load(f)
    if not isinstance(events, list) or not events:
        raise ValueError(f"{path} must contain a non-empty JSON array of events")
    return events
