from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.embedding_cache import EmbeddingCache
from app.services.embeddings import document_embedding_cache_hash


class DocumentService:
    def get_document(
        self, session: Session, *, user_id: UUID, document_id: UUID
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        return session.scalar(statement)

    def list_documents(self, session: Session, *, user_id: UUID) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id)
        )
        return list(session.scalars(statement).all())

    def delete_document(
        self, session: Session, *, user_id: UUID, document_id: UUID
    ) -> Document | None:
        document = self.get_document(session, user_id=user_id, document_id=document_id)
        if document is None:
            return None
        content_hashes = {
            document_embedding_cache_hash(document.filename, chunk.content)
            for chunk in document.chunks
        }
        if content_hashes:
            session.execute(
                delete(EmbeddingCache).where(
                    EmbeddingCache.user_id == user_id,
                    EmbeddingCache.content_hash.in_(content_hashes),
                )
            )
        session.delete(document)
        session.commit()
        return document
