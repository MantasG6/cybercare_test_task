import argparse
import tomllib
from functools import partial

import uvicorn
from pymongo import MongoClient

from consumer.app import create_app
from consumer.event_queue import EventQueue, Store
from consumer.rate_limit import TokenBucket
from consumer.store import save_event


def build_limiter(config: dict) -> TokenBucket:
    rate_limit = {"requests_per_second": 10, "burst": 20} | config.get("rate_limit", {})
    return TokenBucket(rate_limit["requests_per_second"], rate_limit["burst"])


def build_event_queue(config: dict, store: Store) -> EventQueue:
    queue = {"max_size": 20, "workers": 1} | config.get("queue", {})
    return EventQueue(store, queue["max_size"], queue["workers"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Event consumer")
    parser.add_argument("--config", default="config/consumer.toml")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    mongo = config["mongo"]
    collection = MongoClient(mongo["uri"])[mongo["database"]][mongo["collection"]]
    events = build_event_queue(config, partial(save_event, collection))
    app = create_app(collection, build_limiter(config), events)
    uvicorn.run(app, host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
