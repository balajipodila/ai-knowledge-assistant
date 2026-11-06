from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.dependencies import get_embedding_client, get_llm_client
from app.ai.interfaces import EmbeddingClient, LLMClient
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.demo import demo_document_id
from app.core.features import require_ai_features_enabled
from app.core.rate_limits import chat_rate_limit
from app.core.request_id import get_request_id
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    _rate_limit: Annotated[None, Depends(chat_rate_limit)],
) -> ChatResponse:
    require_ai_features_enabled(settings)
    if getattr(request.state, "is_demo_session", False):
        allowed_document_id = demo_document_id(session, user, settings)
        requested_ids = payload.document_ids
        payload = payload.model_copy(
            update={
                "document_ids": (
                    [allowed_document_id]
                    if allowed_document_id is not None
                    and (requested_ids is None or allowed_document_id in requested_ids)
                    else []
                )
            }
        )
    return ChatService(
        embedding_client=embedding_client,
        llm_client=llm_client,
        settings=settings,
    ).answer(
        session,
        user=user,
        request=payload,
        request_id=get_request_id(request),
    )
