from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document


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
