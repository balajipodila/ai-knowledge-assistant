from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.ai.dependencies import get_embedding_client
from app.ai.interfaces import EmbeddingClient
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limits import upload_rate_limit
from app.models.user import User
from app.schemas.documents import DocumentResponse, DocumentUploadResponse
from app.services.documents import DocumentService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import DocumentIngestionService, DocumentUploadError
from app.services.storage import LocalFileStorage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": DocumentUploadResponse}},
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    response: Response,
    _rate_limit: Annotated[None, Depends(upload_rate_limit)],
) -> DocumentUploadResponse:
    data = await file.read(settings.max_upload_size_bytes + 1)
    if len(data) > settings.max_upload_size_bytes:
        raise DocumentUploadError(
            413, "FILE_TOO_LARGE", "The uploaded file exceeds the configured size limit."
        )
    document, chunk_count, duplicate = DocumentIngestionService(
        storage=LocalFileStorage(settings.upload_directory),
        settings=settings,
        embedding_client=embedding_client,
    ).upload(
        session,
        user=user,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        page_count=document.page_count,
        created_at=document.created_at,
        failure_reason=document.failure_reason,
        chunk_count=chunk_count,
        duplicate=duplicate,
    )


@router.post("/{document_id}/retry-embedding", response_model=DocumentResponse)
def retry_document_embedding(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
) -> DocumentResponse:
    document_service = DocumentService()
    document = document_service.get_document(
        session, user_id=user.id, document_id=document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "embedding_failed":
        raise HTTPException(
            status_code=409,
            detail="This document does not need an embedding retry.",
        )

    updated = EmbeddingService(
        client=embedding_client,
        settings=settings,
    ).embed_document(
        session,
        document_id=document.id,
        user_id=user.id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(updated)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[DocumentResponse]:
    documents = DocumentService().list_documents(session, user_id=user.id)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    document = DocumentService().get_document(
        session, user_id=user.id, document_id=document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    service = DocumentService()
    document = service.get_document(
        session, user_id=user.id, document_id=document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.storage_key is not None:
        LocalFileStorage(settings.upload_directory).delete(document.storage_key)
    service.delete_document(
        session, user_id=user.id, document_id=document_id
    )
