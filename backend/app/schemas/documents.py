from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: str
    page_count: int
    created_at: datetime
    failure_reason: str | None = None


class DocumentUploadResponse(DocumentResponse):
    chunk_count: int
    duplicate: bool = False
