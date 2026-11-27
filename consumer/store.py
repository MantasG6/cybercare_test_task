from datetime import UTC, datetime

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from consumer.models import Event


def create_indexes(collection: Collection) -> None:
    # Partial, so events sent without a key are not affected.
    collection.create_index(
        "idempotency_key",
        unique=True,
        partialFilterExpression={"idempotency_key": {"$exists": True}},
    )


def save_event(collection: Collection, event: Event, idempotency_key: str | None = None) -> None:
    document = {**event.model_dump(), "received_at": datetime.now(UTC)}
    if idempotency_key is not None:
        document["idempotency_key"] = idempotency_key
    try:
        collection.insert_one(document)
    except DuplicateKeyError:
        pass  # Already stored under this key.
