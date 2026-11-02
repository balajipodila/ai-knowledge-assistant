from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.constants import EMBEDDING_DIMENSION
from app.models.base import Base


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_embedding_cache_user_id_users",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    content_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
