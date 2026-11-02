"""Add embedding cache, model provenance, and retryable embedding state.

Revision ID: 0004_embeddings_and_search
Revises: 0003_document_ingestion
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0004_embeddings_and_search"
down_revision = "0003_document_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'processing', 'ready', 'failed', 'embedding_failed')",
    )
    op.add_column(
        "chunks",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
    )
    op.create_table(
        "embedding_cache",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_embedding_cache_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "content_hash",
            "model_name",
            name="pk_embedding_cache",
        ),
    )


def downgrade() -> None:
    op.execute(
        "UPDATE documents SET status = 'failed' WHERE status = 'embedding_failed'"
    )
    op.drop_table("embedding_cache")
    op.drop_column("chunks", "embedding_model")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'processing', 'ready', 'failed')",
    )
