from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.database import create_database_engine


def verify_pgvector(engine: Engine) -> str:
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()

    if version is None:
        raise RuntimeError(
            "The pgvector extension is not enabled. Review and apply the approved "
            "Alembic migration before checking the database."
        )

    return version


def main() -> None:
    engine = create_database_engine()
    version = verify_pgvector(engine)
    print(f"Connected to the database; pgvector extension version: {version}")


if __name__ == "__main__":
    main()
