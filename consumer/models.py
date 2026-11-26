from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_type: str
    event_payload: str
