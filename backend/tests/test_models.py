from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint

from app.models import Base, EmbeddingCache
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User


def test_user_scoped_schema_constraints_and_indexes() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "documents",
        "chunks",
        "embedding_cache",
    }

    assert Document.__table__.c.user_id.nullable is False
    assert any(
        constraint.name == "uq_documents_id_user_id"
        for constraint in Document.__table_args__
        if isinstance(constraint, UniqueConstraint)
    )
    assert any(
        foreign_key.ondelete == "CASCADE"
        for foreign_key in Document.__table__.c.user_id.foreign_keys
    )

    assert Chunk.__table__.c.user_id.nullable is False
    embedding_type = Chunk.__table__.c.embedding.type
    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == 768
    assert Chunk.__table__.c.embedding_model.nullable is True
    assert any(
        constraint.name == "fk_chunks_document_user"
        and constraint.ondelete == "CASCADE"
        for constraint in Chunk.__table_args__
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert any(
        index.name == "ix_chunks_embedding_cosine"
        and index.dialect_options["postgresql"]["using"] == "hnsw"
        for index in Chunk.__table_args__
        if isinstance(index, Index)
    )
    assert any(
        index.name == "uq_users_email_normalized" and index.unique
        for index in User.__table_args__
        if isinstance(index, Index)
    )
    cache_embedding_type = EmbeddingCache.__table__.c.embedding.type
    assert isinstance(cache_embedding_type, Vector)
    assert cache_embedding_type.dim == 768
    assert all(
        EmbeddingCache.__table__.c[column_name].primary_key
        for column_name in ("user_id", "content_hash", "model_name")
    )
    assert any(
        foreign_key.ondelete == "CASCADE"
        for foreign_key in EmbeddingCache.__table__.c.user_id.foreign_keys
    )


def test_user_email_is_normalized_before_persistence() -> None:
    user = User(email="  EXAMPLE@EXAMPLE.COM ", password_hash="test-hash")

    assert user.email == "example@example.com"
