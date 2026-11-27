import argparse
import tomllib

import uvicorn
from pymongo import MongoClient

from consumer.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Event consumer")
    parser.add_argument("--config", default="config/consumer.toml")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    mongo = config["mongo"]
    collection = MongoClient(mongo["uri"])[mongo["database"]][mongo["collection"]]
    uvicorn.run(create_app(collection), host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
