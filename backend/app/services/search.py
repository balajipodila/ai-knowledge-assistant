from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document


class SearchService:
    def search(
        self,
        session: Session,
        *,
        user_id: UUID,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int,
        min_similarity: float,
        document_ids: list[UUID] | None = None,
    ) -> list[tuple[Chunk, Document, float]]:
        if document_ids == []:
            return []

        distance = Chunk.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")
        statement = (
            select(Chunk, Document, similarity)
            .join(
                Document,
                and_(
                    Chunk.document_id == Document.id,
                    Chunk.user_id == Document.user_id,
                ),
            )
            .where(
                Chunk.user_id == user_id,
                Document.user_id == user_id,
                Document.status == "ready",
                Chunk.embedding.is_not(None),
                Chunk.embedding_model == embedding_model,
                distance <= 1 - min_similarity,
            )
            .order_by(distance.asc())
            .limit(top_k)
        )
        if document_ids is not None:
            statement = statement.where(Document.id.in_(document_ids))
        return [
            (chunk, document, float(score))
            for chunk, document, score in session.execute(statement).all()
        ]
