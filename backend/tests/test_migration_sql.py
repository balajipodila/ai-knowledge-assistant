import io
from contextlib import redirect_stdout
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_initial_migration_generates_reviewable_sql_offline() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    output = io.StringIO()

    with redirect_stdout(output):
        command.upgrade(config, "head", sql=True)

    sql = output.getvalue().lower()
    assert "create extension if not exists vector" in sql
    assert "create table users" in sql
    assert "create table documents" in sql
    assert "create table chunks" in sql
    assert "lower(btrim(email))" in sql
    assert "content text not null" in sql
    assert "vector(768)" in sql
    assert "on delete cascade" in sql
    assert "using hnsw" in sql
    assert "vector_cosine_ops" in sql
    assert "alter table users add column password_hash varchar(255) default '' not null" in sql
    assert "alter table users alter column password_hash drop default" in sql
    assert "alter table chunks alter column embedding drop not null" in sql
    assert "add column page_number integer default '1' not null" in sql
    assert "add column content_hash char(64)" in sql
    assert "add column failure_reason text" in sql
    assert "uq_documents_user_content_hash" in sql
    assert "embedding_failed" in sql
    assert "add column embedding_model varchar(100)" in sql
    assert "create table embedding_cache" in sql
    assert "vector(768)" in sql
    assert "fk_embedding_cache_user_id_users" in sql
