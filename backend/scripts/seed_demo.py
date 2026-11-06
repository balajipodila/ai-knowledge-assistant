"""Manually seed the read-only demo user and one sample PDF.

Run this script once per environment with the operator's configured database
and Gemini credentials. Visitors receive sessions only; they never run this
script or trigger document ingestion.
"""

import argparse
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.dependencies import get_embedding_client
from app.core.config import get_settings
from app.core.database import create_database_engine
from app.core.passwords import hash_password
from app.models import Document, User
from app.services.ingestion import DocumentIngestionService
from app.services.storage import create_file_storage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pdf",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("demo_sample.pdf"),
        help="Path to the non-personal sample PDF (defaults to demo_sample.pdf)",
    )
    parser.add_argument("--filename", default="demo-sample.pdf")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    if not settings.demo_mode:
        raise SystemExit("DEMO_MODE must be true before seeding the demo.")
    if not args.pdf.is_file():
        raise SystemExit(f"Sample PDF does not exist: {args.pdf}")

    engine = create_database_engine(settings)
    with Session(engine) as session:
        user = session.scalar(
            select(User).where(User.email == settings.demo_user_email)
        )
        if user is None:
            user = User(
                id=uuid4(),
                email=settings.demo_user_email,
                password_hash=hash_password(token_urlsafe()),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        existing = session.scalar(
            select(Document).where(
                Document.user_id == user.id,
                Document.filename == args.filename,
            )
        )
        if existing is not None:
            print(f"Demo document already exists: {existing.id}")
            return

        client = get_embedding_client(settings)
        document, _, _ = DocumentIngestionService(
            storage=create_file_storage(settings),
            settings=settings,
            embedding_client=client,
        ).upload(
            session,
            user=user,
            filename=args.filename,
            content_type="application/pdf",
            data=args.pdf.read_bytes(),
        )
        print(f"Seeded demo document: {document.id}")


if __name__ == "__main__":
    main()
