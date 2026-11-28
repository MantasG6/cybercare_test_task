import math
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pymongo.collection import Collection

from consumer.event_queue import EventQueue
from consumer.models import Event
from consumer.rate_limit import TokenBucket
from consumer.store import create_indexes


def create_app(collection: Collection, limiter: TokenBucket, events: EventQueue) -> FastAPI:
    create_indexes(collection)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        events.start()
        yield
        events.stop()

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path == "/event":
            wait = limiter.acquire()
            if wait:
                return Response(status_code=429, headers={"Retry-After": str(max(1, math.ceil(wait)))})
        return await call_next(request)

    @app.post("/event", status_code=202)
    def post_event(event: Event, idempotency_key: Annotated[str | None, Header()] = None) -> None:
        if not events.put(event, idempotency_key):
            raise HTTPException(503, headers={"Retry-After": "1"})

    return app
