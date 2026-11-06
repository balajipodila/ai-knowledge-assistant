from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document
from app.models.user import User


def is_demo_user(user: User, settings: Settings) -> bool:
    return user.email.strip().lower() == settings.demo_user_email


def ensure_demo_mode(settings: Settings) -> None:
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demo is not currently available.",
        )


def ensure_writable_user(user: User, settings: Settings) -> None:
    if is_demo_user(user, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The demo account is read-only.",
        )


def max_documents_per_user(settings: Settings) -> int:
    return (
        settings.demo_max_documents_per_user
        if settings.demo_mode
        else settings.max_documents_per_user
    )


def max_pdf_pages(settings: Settings) -> int:
    return (
        min(settings.max_pdf_pages, settings.demo_max_pdf_pages)
        if settings.demo_mode
        else settings.max_pdf_pages
    )


def global_demo_caps_reached(user_count: int, document_count: int, settings: Settings) -> str | None:
    if not settings.demo_mode:
        return None
    if user_count >= settings.demo_max_users:
        return "The public demo has reached its user limit. Please try again later."
    if document_count >= settings.demo_max_documents:
        return "The public demo has reached its document limit. Please try again later."
    return None


def demo_document_id(
    session: Session,
    user: User,
    settings: Settings,
) -> UUID | None:
    if settings.demo_document_id:
        try:
            configured_id = UUID(settings.demo_document_id)
        except ValueError:
            return None
        return session.scalar(
            select(Document.id).where(
                Document.id == configured_id,
                Document.user_id == user.id,
            )
        )
    return session.scalar(
        select(Document.id)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at, Document.id)
        .limit(1)
    )
