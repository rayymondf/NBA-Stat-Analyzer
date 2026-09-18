"""Public response envelopes used to keep OpenAPI responses explicit.

Domain services intentionally return heterogeneous analytics payloads. These
JSON-root models validate that the public boundary remains serializable while
the frontend's richer named interfaces document individual payload shapes.
"""

from pydantic import BaseModel, JsonValue, RootModel


class JsonObject(RootModel[dict[str, JsonValue]]):
    pass


class JsonObjectList(RootModel[list[dict[str, JsonValue]]]):
    pass


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    request_id: str
    retryable: bool
