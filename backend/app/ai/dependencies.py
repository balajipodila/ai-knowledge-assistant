from typing import Annotated

from fastapi import Depends

from app.ai.gemini import GeminiEmbeddingClient, GeminiLLMClient
from app.ai.interfaces import EmbeddingClient, LLMClient
from app.core.config import Settings, get_settings


def get_embedding_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingClient:
    return GeminiEmbeddingClient(settings)


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMClient:
    return GeminiLLMClient(settings)
