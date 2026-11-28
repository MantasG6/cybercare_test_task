import math

from typing import Annotated

from fastapi import FastAPI, Header, Request, Response
from pymongo.collection import Collection

from consumer.models import Event
from consumer.rate_limit import TokenBucket
from consumer.store import create_indexes, save_event


def create_app(collection: Collection, limiter: TokenBucket) -> FastAPI:
    create_indexes(collection)
    app = FastAPI()

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path == "/event":
            wait = limiter.acquire()
            if wait:
                return Response(status_code=429, headers={"Retry-After": str(max(1, math.ceil(wait)))})
        return await call_next(request)

    @app.post("/event", status_code=201)
    def post_event(event: Event, idempotency_key: Annotated[str | None, Header()] = None) -> None:
        save_event(collection, event, idempotency_key)

    return app
