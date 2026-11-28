import math

from contextlib import asynccontextmanager
from typing import Annotated

import anyio.to_thread
from fastapi import FastAPI, Header, HTTPException, Request, Response
from pymongo.collection import Collection

from consumer.models import Event
from consumer.rate_limit import TokenBucket
from consumer.store import create_indexes, save_event


def create_app(collection: Collection, limiter: TokenBucket, max_in_flight: int) -> FastAPI:
    create_indexes(collection)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Size the shared worker thread pool to the cap on concurrent /event requests.
        anyio.to_thread.current_default_thread_limiter().total_tokens = max_in_flight
        yield

    app = FastAPI(lifespan=lifespan)
    in_flight = 0

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path == "/event":
            wait = limiter.acquire()
            if wait:
                return Response(status_code=429, headers={"Retry-After": str(max(1, math.ceil(wait)))})
        return await call_next(request)

    @app.post("/event", status_code=201)
    async def post_event(event: Event, idempotency_key: Annotated[str | None, Header()] = None) -> None:
        # Count only the store call, so slow uploads and invalid events never hold a slot.
        # No await between the check and the increment, so the event loop needs no lock.
        nonlocal in_flight
        if in_flight >= max_in_flight:
            # Nothing was stored, so the request should not count against the rate limit either.
            limiter.release()
            # No Retry-After, so the Propagator's doubling backoff applies while the overload lasts.
            raise HTTPException(status_code=503)
        in_flight += 1
        try:
            await anyio.to_thread.run_sync(save_event, collection, event, idempotency_key)
        finally:
            in_flight -= 1

    return app
