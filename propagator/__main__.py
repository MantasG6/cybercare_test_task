import argparse
import logging
import tomllib

import httpx

from propagator.events import load_events
from propagator.sender import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Event propagator")
    parser.add_argument("--config", default="config/propagator.toml")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with httpx.Client() as client:
        run(client, config["endpoint_url"], load_events(config["events_file"]), config["interval_seconds"])


if __name__ == "__main__":
    main()
