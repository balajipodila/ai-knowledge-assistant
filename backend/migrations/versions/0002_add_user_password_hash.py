"""Add password hashes for local account authentication.

Revision ID: 0002_add_user_password_hash
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_user_password_hash"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            server_default="",
            nullable=False,
        ),
    )
    op.alter_column("users", "password_hash", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
