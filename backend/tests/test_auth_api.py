from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.tokens import JWT_ALGORITHM
from app.main import app
from app.models.user import User

TEST_SECRET = "test-only-signing-key-with-at-least-32-bytes"
SIGNUP_BODY = {"email": "Person@Example.com", "password": "a secure password"}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    test_session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY=TEST_SECRET,
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    )

    def override_db() -> Generator[Session, None, None]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_session_factory = test_session_factory
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        del app.state.test_session_factory
        engine.dispose()


def _signup(client: TestClient) -> dict[str, Any]:
    response = client.post("/auth/signup", json=SIGNUP_BODY)
    assert response.status_code == 201
    return response.json()


def test_signup_stores_only_argon2id_hash_and_returns_access_token(
    client: TestClient,
) -> None:
    response = client.post("/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 1800
    assert payload["user"]["email"] == "person@example.com"
    assert payload["user"]["id"]
    assert SIGNUP_BODY["password"] not in response.text

    with client.app.state.test_session_factory() as session:
        user = session.query(User).one()

    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != SIGNUP_BODY["password"]


def test_duplicate_signup_returns_conflict(client: TestClient) -> None:
    _signup(client)

    response = client.post(
        "/auth/signup",
        json={"email": " person@example.com ", "password": "another secure password"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_login_success_returns_access_token(client: TestClient) -> None:
    _signup(client)

    response = client.post(
        "/auth/login",
        json={"email": "PERSON@example.com", "password": SIGNUP_BODY["password"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["email"] == "person@example.com"


def test_login_failure_is_identical_for_unknown_email_and_bad_password(
    client: TestClient,
) -> None:
    _signup(client)
    bad_password = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "wrong password"},
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong password"},
    )

    assert bad_password.status_code == unknown_email.status_code == 401
    assert bad_password.json()["error"]["code"] == unknown_email.json()["error"]["code"]
    assert (
        bad_password.json()["error"]["message"]
        == unknown_email.json()["error"]["message"]
    )


def test_me_requires_token_and_returns_current_user(client: TestClient) -> None:
    signup = _signup(client)

    unauthorized = client.get("/auth/me")
    authorized = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {signup['access_token']}"},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
    assert authorized.status_code == 200
    assert authorized.json()["id"] == signup["user"]["id"]
    assert authorized.json()["email"] == signup["user"]["email"]


@pytest.mark.parametrize("token", ["not.a.valid.token", ""])
def test_me_rejects_invalid_or_empty_token(client: TestClient, token: str) -> None:
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_rejects_expired_token(client: TestClient) -> None:
    signup = _signup(client)
    user_id = signup["user"]["id"]
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": user_id,
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        TEST_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_rejects_token_signed_with_another_secret(client: TestClient) -> None:
    signup = _signup(client)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": signup["user"]["id"],
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        "another-test-key-that-is-at-least-32-bytes",
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "a secure password"},
        {"email": "person@example.com", "password": "short"},
        {"email": "person@example.com", "password": "x" * 129},
    ],
)
def test_signup_validates_email_and_password(body: dict[str, str], client: TestClient) -> None:
    response = client.post("/auth/signup", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
