from typing import Annotated

from fastapi import FastAPI, Header
from pymongo.collection import Collection

from consumer.models import Event
from consumer.store import create_indexes, save_event


def create_app(collection: Collection) -> FastAPI:
    create_indexes(collection)
    app = FastAPI()

    @app.post("/event", status_code=201)
    def post_event(event: Event, idempotency_key: Annotated[str | None, Header()] = None) -> None:
        save_event(collection, event, idempotency_key)

    return app
