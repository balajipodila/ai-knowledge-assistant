from collections.abc import Generator
from math import sqrt
import os
from typing import Protocol, cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.ai.dependencies import get_embedding_client, get_llm_client
from app.ai.fakes import FakeEmbeddingClient, FakeLLMClient
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.main import create_app
from app.models import Chunk, Document, User

pytestmark = pytest.mark.postgres_vector

_TEST_SECRET = "test-only-signing-key-with-at-least-32-bytes"


class SearchHttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
    ) -> httpx.Response: ...


class FixedQueryEmbeddingClient(FakeEmbeddingClient):
    def embed(self, text: str) -> list[float]:
        del text
        return [1.0, *([0.0] * (self.dimension - 1))]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


def _same_database(first: str, second: str) -> bool:
    first_url: URL = make_url(first)
    second_url: URL = make_url(second)
    return (
        first_url.host == second_url.host
        and first_url.port == second_url.port
        and first_url.database == second_url.database
    )


@pytest.fixture(scope="module")
def postgres_factory() -> Generator[sessionmaker[Session], None, None]:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip(
            "Vector search integration tests skipped: TEST_DATABASE_URL is not set."
        )

    main_url = os.environ.get("DATABASE_URL")
    if main_url is not None and _same_database(test_url, main_url):
        pytest.fail(
            "TEST_DATABASE_URL resolves to DATABASE_URL; refusing to run vector tests.",
            pytrace=False,
        )

    engine = create_engine(test_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            revision = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one_or_none()
            extension = connection.exec_driver_sql(
                "SELECT extname FROM pg_extension WHERE extname = 'vector'"
            ).scalar_one_or_none()
        if revision != "0004_embeddings_and_search" or extension != "vector":
            pytest.fail(
                "The disposable TEST_DATABASE_URL database must have the M5 "
                "migration and pgvector extension applied.",
                pytrace=False,
            )
    except SQLAlchemyError as error:
        pytest.fail(
            "Could not verify the disposable vector test database "
            f"({type(error).__name__}); connection details are withheld.",
            pytrace=False,
        )

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def _add_document(
    session: Session,
    *,
    owner_id: UUID,
    filename: str,
    status: str,
    content: str,
    embedding: list[float],
) -> UUID:
    document = Document(
        user_id=owner_id,
        filename=filename,
        content_hash=uuid4().hex * 2,
        page_count=1,
        status=status,
    )
    session.add(document)
    session.flush()
    session.add(
        Chunk(
            user_id=owner_id,
            document_id=document.id,
            chunk_index=0,
            page_number=1,
            content=content,
            metadata_json={},
            embedding=embedding,
            embedding_model="gemini-embedding-2",
        )
    )
    session.flush()
    return document.id


def test_search_filters_owner_status_threshold_and_top_k(
    postgres_factory: sessionmaker[Session],
) -> None:
    settings = Settings.model_validate(
        {
            "jwt_secret_key": _TEST_SECRET,
            "search_min_similarity": 0.0,
            "search_max_top_k": 20,
        }
    )
    owner_id = uuid4()
    other_owner_id = uuid4()
    owner_token = create_access_token(owner_id, settings)
    application = create_app(settings=settings)

    def override_db() -> Generator[Session, None, None]:
        with postgres_factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_embedding_client] = FixedQueryEmbeddingClient

    exact_vector = [1.0, *([0.0] * 767)]
    lower_vector = [0.8, 0.6, *([0.0] * 766)]
    other_user_vector = [0.3, sqrt(0.91), *([0.0] * 766)]
    created_document_ids: list[UUID] = []
    try:
        with postgres_factory() as session:
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"{owner_id}@example.test",
                        password_hash=hash_password("test password"),
                    ),
                    User(
                        id=other_owner_id,
                        email=f"{other_owner_id}@example.test",
                        password_hash=hash_password("test password"),
                    ),
                ]
            )
            session.flush()
            created_document_ids.extend(
                [
                    _add_document(
                        session,
                        owner_id=owner_id,
                        filename="best.pdf",
                        status="ready",
                        content="best result",
                        embedding=exact_vector,
                    ),
                    _add_document(
                        session,
                        owner_id=owner_id,
                        filename="second.pdf",
                        status="ready",
                        content="second result",
                        embedding=lower_vector,
                    ),
                    _add_document(
                        session,
                        owner_id=owner_id,
                        filename="processing.pdf",
                        status="processing",
                        content="not searchable",
                        embedding=exact_vector,
                    ),
                    _add_document(
                        session,
                        owner_id=other_owner_id,
                        filename="private.pdf",
                        status="ready",
                        content="belongs to another user",
                        embedding=other_user_vector,
                    ),
                ]
            )
            session.commit()

        with TestClient(application) as test_client:
            client = cast(SearchHttpClient, test_client)
            headers = {"Authorization": f"Bearer {owner_token}"}
            response = client.post(
                "/search",
                json={"query": "find matching content", "top_k": 2},
                headers=headers,
            )
            assert response.status_code == 200
            results = response.json()["results"]
            assert len(results) == 2
            assert results[0]["document_id"] == str(created_document_ids[0])
            assert results[1]["document_id"] == str(created_document_ids[1])
            assert results[0]["similarity_score"] > results[1]["similarity_score"]
            assert all(
                result["document_id"] != str(created_document_ids[3])
                for result in results
            )
            assert all(
                result["document_id"] != str(created_document_ids[2])
                for result in results
            )

            all_matches = client.post(
                "/search",
                json={"query": "find matching content", "top_k": 5},
                headers=headers,
            )
            assert all_matches.status_code == 200
            assert len(all_matches.json()["results"]) == 2
            assert all(
                result["document_id"] != str(created_document_ids[3])
                for result in all_matches.json()["results"]
            )

            settings.search_min_similarity = 0.85
            filtered = client.post(
                "/search",
                json={"query": "find matching content", "top_k": 5},
                headers=headers,
            )
            assert filtered.status_code == 200
            assert len(filtered.json()["results"]) == 1
            assert (
                filtered.json()["results"][0]["document_id"]
                == str(created_document_ids[0])
            )
    finally:
        application.dependency_overrides.clear()
        with postgres_factory() as session:
            for document in session.scalars(
                select(Document).where(Document.id.in_(created_document_ids))
            ).all():
                session.delete(document)
            for user in session.scalars(
                select(User).where(User.id.in_([owner_id, other_owner_id]))
            ).all():
                session.delete(user)
            session.commit()


def test_chat_does_not_reveal_another_users_document(
    postgres_factory: sessionmaker[Session],
) -> None:
    settings = Settings.model_validate(
        {
            "jwt_secret_key": _TEST_SECRET,
            "search_min_similarity": 0.0,
            "chat_max_context_chunks": 5,
        }
    )
    owner_a_id = uuid4()
    owner_b_id = uuid4()
    document_id = uuid4()
    embedding = [1.0, *([0.0] * 767)]
    llm_client = FakeLLMClient("Private content [1].")
    application = create_app(settings=settings)

    def override_db() -> Generator[Session, None, None]:
        with postgres_factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_embedding_client] = (
        FixedQueryEmbeddingClient
    )
    application.dependency_overrides[get_llm_client] = lambda: llm_client
    try:
        with postgres_factory() as session:
            session.add_all(
                [
                    User(
                        id=owner_a_id,
                        email=f"{owner_a_id}@example.test",
                        password_hash=hash_password("test password"),
                    ),
                    User(
                        id=owner_b_id,
                        email=f"{owner_b_id}@example.test",
                        password_hash=hash_password("test password"),
                    ),
                ]
            )
            session.flush()
            document_id = _add_document(
                session,
                owner_id=owner_a_id,
                filename="private.pdf",
                status="ready",
                content="Private user A content.",
                embedding=embedding,
            )
            session.commit()

        with TestClient(application) as test_client:
            client = cast(SearchHttpClient, test_client)
            headers = {
                "Authorization": f"Bearer {create_access_token(owner_b_id, settings)}"
            }
            without_filter = client.post(
                "/chat",
                json={"question": "What is in my documents?"},
                headers=headers,
            )
            with_foreign_filter = client.post(
                "/chat",
                json={
                    "question": "What is in my documents?",
                    "document_ids": [str(document_id)],
                },
                headers=headers,
            )

        assert without_filter.status_code == 200
        assert with_foreign_filter.status_code == 200
        assert without_filter.json() == with_foreign_filter.json()
        assert without_filter.json() == {
            "answer": "I could not find this in your documents.",
            "citations": [],
        }
        assert llm_client.prompts == []
    finally:
        application.dependency_overrides.clear()
        with postgres_factory() as session:
            session.execute(
                delete(Document).where(Document.id == document_id)
            )
            session.execute(
                delete(User).where(User.id.in_([owner_a_id, owner_b_id]))
            )
            session.commit()
