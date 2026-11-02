from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.errors import EmbeddingProviderError
from app.ai.fakes import FakeEmbeddingClient
from app.core.config import Settings
from app.models import Base, Chunk, Document, EmbeddingCache, User
from app.services.embeddings import (
    EmbeddingService,
    document_embedding_cache_hash,
)


@pytest.fixture
def embedding_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session.add(User(email="embed@example.com", password_hash="test-hash"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create_document(
    session: Session,
    *,
    user: User,
    filename: str = "sample.pdf",
    contents: tuple[str, ...] = ("first chunk", "second chunk"),
) -> Document:
    document = Document(
        user_id=user.id,
        filename=filename,
        content_hash=uuid4().hex * 2,
        page_count=1,
        status="processing",
    )
    session.add(document)
    session.flush()
    session.add_all(
        Chunk(
            user_id=user.id,
            document_id=document.id,
            chunk_index=index,
            page_number=1,
            content=content,
            metadata_json={},
            embedding=None,
        )
        for index, content in enumerate(contents)
    )
    session.commit()
    return document


def _settings(*, batch_size: int = 2) -> Settings:
    return Settings.model_validate(
        {
            "embedding_batch_size": batch_size,
            "embedding_max_attempts": 2,
            "embedding_backoff_base_seconds": 1,
            "embedding_backoff_max_seconds": 3,
            "embedding_batch_delay_seconds": 0,
        }
    )


def test_batch_retry_uses_exponential_backoff(embedding_session: Session) -> None:
    user = embedding_session.scalar(select(User))
    assert user is not None
    document = _create_document(embedding_session, user=user)
    delays: list[float] = []

    class RetryOnceClient(FakeEmbeddingClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[list[str]] = []

        def embed_many(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(texts)
            if len(self.calls) == 1:
                raise EmbeddingProviderError(
                    "rate limited",
                    retryable=True,
                    status_code=429,
                )
            return super().embed_many(texts)

    client = RetryOnceClient()
    result = EmbeddingService(
        client=client,
        settings=_settings(),
        sleep=delays.append,
    ).embed_document(
        embedding_session,
        document_id=document.id,
        user_id=user.id,
    )

    assert result is not None
    assert result.status == "ready"
    assert len(client.calls) == 2
    assert len(delays) == 1
    assert 1 <= delays[0] <= 1.25
    chunks = embedding_session.scalars(
        select(Chunk).where(Chunk.document_id == document.id)
    ).all()
    assert all(chunk.embedding is not None for chunk in chunks)


def test_embedding_cache_prevents_duplicate_provider_call(
    embedding_session: Session,
) -> None:
    user = embedding_session.scalar(select(User))
    assert user is not None
    first = _create_document(
        embedding_session, user=user, contents=("repeated content",)
    )
    second = _create_document(
        embedding_session, user=user, contents=("repeated content",)
    )

    class CountingClient(FakeEmbeddingClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[list[str]] = []

        def embed_many(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(texts)
            return super().embed_many(texts)

    client = CountingClient()
    service = EmbeddingService(client=client, settings=_settings())
    service.embed_document(
        embedding_session, document_id=first.id, user_id=user.id
    )
    service.embed_document(
        embedding_session, document_id=second.id, user_id=user.id
    )

    assert len(client.calls) == 1
    second_chunk = embedding_session.scalar(
        select(Chunk).where(Chunk.document_id == second.id)
    )
    assert second_chunk is not None
    assert second_chunk.embedding is not None
    assert embedding_session.scalar(select(EmbeddingCache)) is not None


def test_partial_failure_keeps_chunks_and_retry_embeds_only_missing(
    embedding_session: Session,
) -> None:
    user = embedding_session.scalar(select(User))
    assert user is not None
    document = _create_document(
        embedding_session,
        user=user,
        contents=("already embedded", "needs retry"),
    )

    class FailSecondBatchClient(FakeEmbeddingClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[list[str]] = []
            self.fail_second = True

        def embed_many(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(texts)
            if self.fail_second and len(self.calls) == 2:
                raise EmbeddingProviderError("temporary network failure")
            return super().embed_many(texts)

    client = FailSecondBatchClient()
    settings = _settings(batch_size=1)
    service = EmbeddingService(client=client, settings=settings)
    failed = service.embed_document(
        embedding_session,
        document_id=document.id,
        user_id=user.id,
    )

    assert failed is not None
    assert failed.status == "embedding_failed"
    assert failed.failure_reason == "temporary network failure"
    chunks = embedding_session.scalars(
        select(Chunk)
        .where(Chunk.document_id == document.id)
        .order_by(Chunk.chunk_index)
    ).all()
    assert len(chunks) == 2
    assert chunks[0].embedding is not None
    assert chunks[1].embedding is None

    first_chunk_hash = document_embedding_cache_hash(
        document.filename, chunks[0].content
    )
    embedding_session.execute(
        delete(EmbeddingCache).where(
            EmbeddingCache.user_id == user.id,
            EmbeddingCache.content_hash == first_chunk_hash,
        )
    )
    embedding_session.commit()

    client.fail_second = False
    calls_before_retry = len(client.calls)
    retried = service.embed_document(
        embedding_session,
        document_id=document.id,
        user_id=user.id,
    )

    assert retried is not None
    assert retried.status == "ready"
    assert len(client.calls) == calls_before_retry + 1
    assert client.calls[-1] == [
        "title: sample.pdf | text: needs retry"
    ]
    assert all(chunk.embedding is not None for chunk in chunks)
