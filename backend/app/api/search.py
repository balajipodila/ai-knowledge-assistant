from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.ai.dependencies import get_embedding_client
from app.ai.errors import EmbeddingProviderError
from app.ai.interfaces import EmbeddingClient
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.demo import demo_document_id
from app.core.features import require_ai_features_enabled
from app.core.rate_limits import search_rate_limit
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import EmbeddingService
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_documents(
    request: Request,
    payload: SearchRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    _rate_limit: Annotated[None, Depends(search_rate_limit)],
) -> SearchResponse:
    require_ai_features_enabled(settings)
    if getattr(request.state, "is_demo_session", False):
        allowed_document_id = demo_document_id(session, user, settings)
        payload = payload.model_copy(
            update={
                "document_ids": (
                    [allowed_document_id]
                    if allowed_document_id is not None
                    and (
                        payload.document_ids is None
                        or allowed_document_id in payload.document_ids
                    )
                    else []
                )
            }
        )
    if payload.top_k > settings.search_max_top_k:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="top_k exceeds the configured maximum.",
        )

    try:
        query_embedding = EmbeddingService(
            client=embedding_client,
            settings=settings,
        ).embed_query(payload.query)
    except EmbeddingProviderError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable.",
        ) from None

    rows = SearchService().search(
        session,
        user_id=user.id,
        query_embedding=query_embedding,
        embedding_model=settings.gemini_embedding_model,
        top_k=payload.top_k,
        min_similarity=(
            payload.min_similarity
            if payload.min_similarity is not None
            else settings.search_min_similarity
        ),
        document_ids=payload.document_ids,
    )
    return SearchResponse(
        results=[
            SearchResult(
                document_id=document.id,
                filename=document.filename,
                page_number=chunk.page_number,
                chunk_text=chunk.content,
                similarity_score=score,
            )
            for chunk, document, score in rows
        ]
    )
