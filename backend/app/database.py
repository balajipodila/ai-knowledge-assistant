import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def create_database_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add your Neon connection URL to the root .env file."
        )

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    return create_engine(database_url, pool_pre_ping=True)


def verify_pgvector(engine: Engine) -> str:
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()

    if version is None:
        raise RuntimeError(
            "The pgvector extension is not enabled. Run "
            "'CREATE EXTENSION IF NOT EXISTS vector;' in the Neon SQL Editor."
        )

    return version


def main() -> None:
    engine = create_database_engine()
    version = verify_pgvector(engine)
    print(f"Connected to the database; pgvector extension version: {version}")


if __name__ == "__main__":
    main()
