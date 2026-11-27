import json
from pathlib import Path


def load_events(path: str | Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)
