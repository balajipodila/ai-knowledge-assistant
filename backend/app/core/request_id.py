from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"


def create_request_id() -> str:
    return str(uuid4())


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")
