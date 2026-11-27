from fastapi import FastAPI
from pymongo.collection import Collection

from consumer.models import Event
from consumer.store import save_event


def create_app(collection: Collection) -> FastAPI:
    app = FastAPI()

    @app.post("/event", status_code=201)
    def post_event(event: Event) -> None:
        save_event(collection, event)

    return app
