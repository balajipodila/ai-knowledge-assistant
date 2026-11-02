from typing import Annotated

from fastapi import Depends

from app.ai.gemini import GeminiEmbeddingClient
from app.ai.interfaces import EmbeddingClient
from app.core.config import Settings, get_settings


def get_embedding_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingClient:
    return GeminiEmbeddingClient(settings)
