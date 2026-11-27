import argparse
import tomllib

import uvicorn
from pymongo import MongoClient

from consumer.app import create_app
from consumer.rate_limit import TokenBucket


def build_limiter(config: dict) -> TokenBucket:
    rate_limit = {"requests_per_second": 10, "burst": 20} | config.get("rate_limit", {})
    return TokenBucket(rate_limit["requests_per_second"], rate_limit["burst"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Event consumer")
    parser.add_argument("--config", default="config/consumer.toml")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    mongo = config["mongo"]
    collection = MongoClient(mongo["uri"])[mongo["database"]][mongo["collection"]]
    uvicorn.run(create_app(collection, build_limiter(config)), host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
