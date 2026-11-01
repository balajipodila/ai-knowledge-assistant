from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.core.request_id import REQUEST_ID_HEADER, create_request_id


def _client_with_error_routes() -> TestClient:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="private detail")

    @application.get("/crash")
    def crash() -> None:
        raise RuntimeError("private exception detail")

    @application.get("/invalid/{item_id}")
    def invalid(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @application.middleware("http")
    async def set_request_id(request, call_next):
        request.state.request_id = create_request_id()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    return TestClient(application, raise_server_exceptions=False)


def test_http_error_uses_stable_safe_response() -> None:
    response = _client_with_error_routes().get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "The requested resource was not found."
    assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "private detail" not in response.text


def test_framework_not_found_uses_stable_error_shape() -> None:
    response = _client_with_error_routes().get("/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unhandled_error_does_not_expose_exception_details() -> None:
    response = _client_with_error_routes().get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "private exception detail" not in response.text
    assert "Traceback" not in response.text


def test_validation_error_does_not_echo_submitted_value() -> None:
    response = _client_with_error_routes().get("/invalid/not-an-integer")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "not-an-integer" not in response.text
