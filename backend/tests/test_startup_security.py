import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    "secret",
    [
        None,
        "replace-with-a-random-secret-at-least-32-bytes",
        "change-me-but-this-is-more-than-thirty-two-bytes",
        "too-short",
    ],
)
def test_application_refuses_startup_without_a_real_jwt_secret(
    secret: str | None,
) -> None:
    settings = Settings(_env_file=None, JWT_SECRET_KEY=secret)
    application = create_app(settings=settings)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        with TestClient(application):
            pass


def test_application_starts_with_configured_jwt_secret() -> None:
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-only-signing-key-with-at-least-32-bytes",
    )

    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
