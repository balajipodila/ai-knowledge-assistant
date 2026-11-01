"""Add PDF ingestion fields and allow pending embeddings.

Revision ID: 0003_document_ingestion
Revises: 0002_add_user_password_hash
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0003_document_ingestion"
down_revision = "0002_add_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("chunks", "embedding", existing_type=Vector(768), nullable=True)
    op.add_column(
        "chunks",
        sa.Column("page_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.alter_column("chunks", "page_number", server_default=None)
    op.create_check_constraint(
        "ck_chunks_positive_page_number", "chunks", "page_number >= 1"
    )

    op.add_column("documents", sa.Column("content_hash", sa.CHAR(length=64)))
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("documents", "page_count", server_default=None)
    op.add_column("documents", sa.Column("failure_reason", sa.Text()))
    op.add_column("documents", sa.Column("storage_key", sa.String(length=255)))
    op.create_check_constraint(
        "ck_documents_nonnegative_page_count", "documents", "page_count >= 0"
    )
    op.create_index(
        "uq_documents_user_content_hash",
        "documents",
        ["user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
        sqlite_where=sa.text("content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_user_content_hash", table_name="documents")
    op.drop_constraint(
        "ck_documents_nonnegative_page_count", "documents", type_="check"
    )
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "failure_reason")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "content_hash")
    op.drop_constraint("ck_chunks_positive_page_number", "chunks", type_="check")
    op.drop_column("chunks", "page_number")
    op.alter_column("chunks", "embedding", existing_type=Vector(768), nullable=False)
