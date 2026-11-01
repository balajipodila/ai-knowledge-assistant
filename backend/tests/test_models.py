from app.models import Base
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User


def test_user_scoped_schema_constraints_and_indexes() -> None:
    assert set(Base.metadata.tables) == {"users", "documents", "chunks"}

    document = Document.__table__
    assert document.c.user_id.nullable is False
    assert any(
        constraint.name == "uq_documents_id_user_id"
        for constraint in document.constraints
    )
    assert any(
        foreign_key.ondelete == "CASCADE"
        for foreign_key in document.c.user_id.foreign_keys
    )

    chunk = Chunk.__table__
    assert chunk.c.user_id.nullable is False
    assert chunk.c.embedding.type.dim == 768
    assert any(
        constraint.name == "fk_chunks_document_user"
        and constraint.ondelete == "CASCADE"
        for constraint in chunk.constraints
    )
    assert any(
        index.name == "ix_chunks_embedding_cosine"
        and index.dialect_options["postgresql"]["using"] == "hnsw"
        for index in chunk.indexes
    )
    assert any(
        index.name == "uq_users_email_normalized" and index.unique
        for index in User.__table__.indexes
    )


def test_user_email_is_normalized_before_persistence() -> None:
    user = User(email="  EXAMPLE@EXAMPLE.COM ")

    assert user.email == "example@example.com"
