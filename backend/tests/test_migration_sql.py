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
