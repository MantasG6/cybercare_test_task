import math

from fastapi import FastAPI, Request, Response
from pymongo.collection import Collection

from consumer.models import Event
from consumer.rate_limit import TokenBucket
from consumer.store import save_event


def create_app(collection: Collection, limiter: TokenBucket) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path == "/event":
            wait = limiter.acquire()
            if wait:
                return Response(status_code=429, headers={"Retry-After": str(max(1, math.ceil(wait)))})
        return await call_next(request)

    @app.post("/event", status_code=201)
    def post_event(event: Event) -> None:
        save_event(collection, event)

    return app
