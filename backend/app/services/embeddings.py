import hashlib
import random
import time
from collections.abc import Callable
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ai.errors import EmbeddingProviderError
from app.ai.interfaces import EmbeddingClient
from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.embedding_cache import EmbeddingCache

logger = structlog.get_logger(__name__)


def prepare_document_input(filename: str, text: str) -> str:
    return f"title: {filename} | text: {text}"


def prepare_search_query(query: str) -> str:
    return f"task: search result | query: {query}"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_embedding_cache_hash(filename: str, text: str) -> str:
    return _content_hash(prepare_document_input(filename, text))


class EmbeddingService:
    def __init__(
        self,
        *,
        client: EmbeddingClient,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.settings = settings
        self._sleep = sleep

    def embed_query(self, query: str) -> list[float]:
        vectors = self._embed_with_retry([prepare_search_query(query)])
        return vectors[0]

    def embed_document(
        self,
        session: Session,
        *,
        document_id: UUID,
        user_id: UUID,
    ) -> Document | None:
        document = session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        if document is None:
            return None

        chunks = list(
            session.scalars(
                select(Chunk)
                .where(
                    Chunk.document_id == document.id,
                    Chunk.user_id == user_id,
                )
                .order_by(Chunk.chunk_index)
            ).all()
        )
        document.status = "processing"
        document.failure_reason = None
        session.commit()

        if any(
            chunk.embedding is not None
            and chunk.embedding_model != self.settings.gemini_embedding_model
            for chunk in chunks
        ):
            return self._mark_failed(
                session,
                document_id=document.id,
                user_id=user_id,
                reason=(
                    "Some chunks use a different embedding model; a full reindex "
                    "is required before they can be searched."
                ),
            )

        try:
            missing_chunks = [
                chunk for chunk in chunks if chunk.embedding is None
            ]
            for start in range(
                0, len(missing_chunks), self.settings.embedding_batch_size
            ):
                batch = missing_chunks[
                    start : start + self.settings.embedding_batch_size
                ]
                self._embed_batch(
                    session,
                    document=document,
                    chunks=batch,
                    user_id=user_id,
                )
                if (
                    start + self.settings.embedding_batch_size < len(chunks)
                    and self.settings.embedding_batch_delay_seconds > 0
                ):
                    self._sleep(self.settings.embedding_batch_delay_seconds)
        except EmbeddingProviderError as error:
            session.rollback()
            logger.warning(
                "Document embedding failed",
                document_id=str(document_id),
                user_id=str(user_id),
                retryable=error.retryable,
            )
            return self._mark_failed(
                session,
                document_id=document_id,
                user_id=user_id,
                reason=error.safe_message,
            )

        refreshed = session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        if refreshed is None:
            return None

        incomplete = session.scalar(
            select(Chunk.id)
            .where(
                Chunk.document_id == document_id,
                Chunk.user_id == user_id,
                Chunk.embedding.is_(None)
                | Chunk.embedding_model.is_(None)
                | (Chunk.embedding_model != self.settings.gemini_embedding_model),
            )
            .limit(1)
        )
        if incomplete is not None:
            return self._mark_failed(
                session,
                document_id=document_id,
                user_id=user_id,
                reason="One or more chunks are still missing embeddings.",
            )

        refreshed.status = "ready"
        refreshed.failure_reason = None
        session.commit()
        session.refresh(refreshed)
        return refreshed

    def _embed_batch(
        self,
        session: Session,
        *,
        document: Document,
        chunks: list[Chunk],
        user_id: UUID,
    ) -> None:
        model_name = self.settings.gemini_embedding_model
        inputs_by_hash: dict[str, str] = {}
        hashes_by_chunk: list[str] = []
        for chunk in chunks:
            prepared = prepare_document_input(document.filename, chunk.content)
            content_hash = _content_hash(prepared)
            inputs_by_hash.setdefault(content_hash, prepared)
            hashes_by_chunk.append(content_hash)

        cached_entries = session.scalars(
            select(EmbeddingCache).where(
                EmbeddingCache.user_id == user_id,
                EmbeddingCache.model_name == model_name,
                EmbeddingCache.content_hash.in_(inputs_by_hash),
            )
        ).all()
        vectors_by_hash = {
            entry.content_hash: list(entry.embedding) for entry in cached_entries
        }

        for chunk, content_hash in zip(chunks, hashes_by_chunk, strict=True):
            cached = vectors_by_hash.get(content_hash)
            if cached is not None:
                chunk.embedding = cached
                chunk.embedding_model = model_name
        if cached_entries:
            session.commit()

        missing_hashes = [
            content_hash
            for content_hash in inputs_by_hash
            if content_hash not in vectors_by_hash
        ]
        if not missing_hashes:
            return

        missing_inputs = [inputs_by_hash[content_hash] for content_hash in missing_hashes]
        vectors = self._embed_with_retry(missing_inputs)
        if len(vectors) != len(missing_hashes):
            raise EmbeddingProviderError(
                "The embedding provider returned an incomplete batch."
            )
        for content_hash, vector in zip(missing_hashes, vectors, strict=True):
            if len(vector) != self.settings.gemini_embedding_dimension:
                raise EmbeddingProviderError(
                    "The embedding provider returned an unexpected vector dimension."
                )
            vectors_by_hash[content_hash] = vector

        for chunk, content_hash in zip(chunks, hashes_by_chunk, strict=True):
            chunk.embedding = vectors_by_hash[content_hash]
            chunk.embedding_model = model_name
        self._insert_cache_entries(
            session,
            [
                {
                    "user_id": user_id,
                    "content_hash": content_hash,
                    "model_name": model_name,
                    "embedding": vectors_by_hash[content_hash],
                }
                for content_hash in missing_hashes
            ],
        )
        session.commit()

    def _embed_with_retry(self, inputs: list[str]) -> list[list[float]]:
        for attempt in range(self.settings.embedding_max_attempts):
            try:
                vectors = self.client.embed_many(inputs)
                if len(vectors) != len(inputs) or any(
                    len(vector) != self.settings.gemini_embedding_dimension
                    for vector in vectors
                ):
                    raise EmbeddingProviderError(
                        "The embedding provider returned an invalid vector batch."
                    )
                return vectors
            except EmbeddingProviderError as error:
                if not error.retryable or attempt + 1 >= self.settings.embedding_max_attempts:
                    raise
                delay = min(
                    self.settings.embedding_backoff_base_seconds * (2**attempt),
                    self.settings.embedding_backoff_max_seconds,
                )
                if delay > 0:
                    self._sleep(delay + random.uniform(0, delay * 0.25))
        raise AssertionError("Embedding retry loop exited without a result.")

    @staticmethod
    def _insert_cache_entries(
        session: Session, entries: list[dict[str, object]]
    ) -> None:
        if not entries:
            return
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(EmbeddingCache).values(entries)
            statement = statement.on_conflict_do_nothing(
                index_elements=[
                    EmbeddingCache.user_id,
                    EmbeddingCache.content_hash,
                    EmbeddingCache.model_name,
                ]
            )
            session.execute(statement)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(EmbeddingCache).values(entries)
            statement = statement.on_conflict_do_nothing(
                index_elements=[
                    EmbeddingCache.user_id,
                    EmbeddingCache.content_hash,
                    EmbeddingCache.model_name,
                ]
            )
            session.execute(statement)
        else:
            session.add_all(EmbeddingCache(**entry) for entry in entries)

    @staticmethod
    def _mark_failed(
        session: Session,
        *,
        document_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> Document | None:
        document = session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        if document is None:
            return None
        document.status = "embedding_failed"
        document.failure_reason = reason
        session.commit()
        session.refresh(document)
        return document
