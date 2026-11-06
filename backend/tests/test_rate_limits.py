from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limits import (
    RateLimitExceeded,
    RequestRateLimiter,
    _Rule,
    chat_rate_limit,
    enforce_auth_attempt,
    search_rate_limit,
    trusted_client_ip,
    upload_rate_limit,
)
from app.core.request_id import REQUEST_ID_HEADER, create_request_id
from app.models.user import User


def _request_with_client_and_forwarded_for(
    client_ip: str,
    forwarded_for: str,
):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", forwarded_for.encode())],
            "client": (client_ip, 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_forwarded_ip_is_ignored_unless_peer_is_a_trusted_proxy() -> None:
    request = _request_with_client_and_forwarded_for(
        "198.51.100.10", "203.0.113.5"
    )
    settings = Settings(_env_file=None)

    assert trusted_client_ip(request, settings) == "198.51.100.10"

    trusted_settings = Settings(
        _env_file=None,
        TRUSTED_PROXY_CIDRS=["192.0.2.0/24"],
    )
    trusted_request = _request_with_client_and_forwarded_for(
        "192.0.2.12", "203.0.113.5, 192.0.2.11"
    )

    assert trusted_client_ip(trusted_request, trusted_settings) == "203.0.113.5"


def test_empty_trusted_proxy_cidrs_uses_peer_as_shared_ip_bucket() -> None:
    settings = Settings(_env_file=None)
    first = _request_with_client_and_forwarded_for("198.51.100.10", "203.0.113.5")
    second = _request_with_client_and_forwarded_for("198.51.100.10", "203.0.113.6")

    assert trusted_client_ip(first, settings) == "198.51.100.10"
    assert trusted_client_ip(second, settings) == "198.51.100.10"


@pytest.mark.parametrize("action", ["login", "signup"])
def test_auth_email_limit_is_independent_of_shared_ip_bucket(action: str) -> None:
    settings = Settings(
        _env_file=None,
        AUTH_EMAIL_ATTEMPTS_PER_MINUTE=1,
        AUTH_IP_ATTEMPTS_PER_MINUTE=10,
    )
    application = FastAPI()
    application.state.request_rate_limiter = RequestRateLimiter()
    first = _request_with_client_and_forwarded_for("198.51.100.10", "203.0.113.5")
    second = _request_with_client_and_forwarded_for("198.51.100.11", "203.0.113.6")
    first.scope["app"] = application
    second.scope["app"] = application

    enforce_auth_attempt(
        first, email="person@example.test", action=action, settings=settings
    )
    with pytest.raises(RateLimitExceeded):
        enforce_auth_attempt(
            second, email="PERSON@example.test", action=action, settings=settings
        )


def test_forwarded_ip_with_invalid_address_falls_back_to_peer() -> None:
    request = _request_with_client_and_forwarded_for(
        "192.0.2.12", "not-an-ip"
    )
    settings = Settings(_env_file=None, TRUSTED_PROXY_CIDRS=["192.0.2.0/24"])

    assert trusted_client_ip(request, settings) == "192.0.2.12"


@pytest.mark.parametrize("action", ["login", "signup"])
def test_auth_email_bucket_is_normalized_and_ip_bucket_is_separate(
    action: str,
) -> None:
    settings = Settings(
        _env_file=None,
        AUTH_EMAIL_ATTEMPTS_PER_MINUTE=1,
        AUTH_IP_ATTEMPTS_PER_MINUTE=3,
    )
    application = FastAPI()
    application.state.request_rate_limiter = RequestRateLimiter()
    request = _request_with_client_and_forwarded_for("198.51.100.10", "")
    request.scope["app"] = application

    enforce_auth_attempt(
        request,
        email=" Person@Example.Test ",
        action=action,
        settings=settings,
    )
    with pytest.raises(RateLimitExceeded):
        enforce_auth_attempt(
            request,
            email="person@example.test",
            action=action,
            settings=settings,
        )

    enforce_auth_attempt(
        request,
        email="another@example.test",
        action=action,
        settings=settings,
    )
    with pytest.raises(RateLimitExceeded):
        enforce_auth_attempt(
            request,
            email="third@example.test",
            action=action,
            settings=settings,
        )


def test_expired_sliding_window_keys_are_removed() -> None:
    now = [0.0]
    limiter = RequestRateLimiter(cleanup_interval_seconds=10, clock=lambda: now[0])
    rule = _Rule("search", "user-1", 1, 60)
    limiter.consume([rule])
    assert limiter._events

    now[0] = 61.0
    limiter.cleanup_expired()

    assert limiter._events == {}


def test_chat_concurrency_cap_is_released_after_a_request() -> None:
    limiter = RequestRateLimiter()

    assert limiter.try_acquire_concurrent("chat", "user-1", 1)
    assert not limiter.try_acquire_concurrent("chat", "user-1", 1)

    limiter.release_concurrent("chat", "user-1")

    assert limiter.try_acquire_concurrent("chat", "user-1", 1)


def test_rate_limit_has_retry_after_and_does_not_echo_identity() -> None:
    now = [10.0]
    limiter = RequestRateLimiter(cleanup_interval_seconds=10, clock=lambda: now[0])
    rule = _Rule("login", "victim@example.test", 1, 60)
    limiter.consume([rule])

    with pytest.raises(RateLimitExceeded) as error:
        limiter.consume([rule])

    assert error.value.retry_after_seconds == 60
    assert "victim@example.test" not in error.value.message


def _resource_limiter_client() -> TestClient:
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-only-signing-key-with-at-least-32-bytes",
        CHAT_REQUESTS_PER_MINUTE=1,
        UPLOAD_REQUESTS_PER_MINUTE=1,
        SEARCH_REQUESTS_PER_MINUTE=1,
    )
    user = User(
        id=uuid4(),
        email="resource-user@example.test",
        password_hash="test-hash",
    )
    application = FastAPI()
    application.state.request_rate_limiter = RequestRateLimiter()
    register_exception_handlers(application)
    application.dependency_overrides[get_settings] = lambda: settings
    from app.core.auth import get_current_user

    application.dependency_overrides[get_current_user] = lambda: user

    @application.middleware("http")
    async def attach_request_id(request, call_next):
        request.state.request_id = create_request_id()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @application.post("/chat", dependencies=[Depends(chat_rate_limit)])
    def chat() -> dict[str, bool]:
        return {"ok": True}

    @application.post("/documents", dependencies=[Depends(upload_rate_limit)])
    def upload() -> dict[str, bool]:
        return {"ok": True}

    @application.post("/search", dependencies=[Depends(search_rate_limit)])
    def search() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(application)


@pytest.mark.parametrize("path", ["/chat", "/documents", "/search"])
def test_expensive_routes_return_structured_429_with_retry_after(path: str) -> None:
    with _resource_limiter_client() as client:
        assert client.post(path).status_code == 200
        response = client.post(path)

    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert response.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "detail" not in response.json()
