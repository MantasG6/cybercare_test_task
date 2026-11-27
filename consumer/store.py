from datetime import UTC, datetime

from pymongo.collection import Collection

from consumer.models import Event


def save_event(collection: Collection, event: Event) -> None:
    collection.insert_one({**event.model_dump(), "received_at": datetime.now(UTC)})
