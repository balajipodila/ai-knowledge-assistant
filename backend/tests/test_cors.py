from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-only-signing-key-with-at-least-32-bytes",
    )
    return TestClient(create_app(settings=settings))


def test_cors_preflight_allows_configured_frontend_origin() -> None:
    client = _client()
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "Access-Control-Allow-Credentials" not in response.headers
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]

    actual_response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert actual_response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"
    assert actual_response.headers["X-Request-ID"]


def test_cors_preflight_rejects_unconfigured_origin() -> None:
    response = _client().options(
        "/auth/login",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 400
    assert "Access-Control-Allow-Origin" not in response.headers
