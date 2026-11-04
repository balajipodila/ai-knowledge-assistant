from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question must not be blank.")
        return normalized


class ChatCitation(BaseModel):
    number: int
    document_id: UUID
    filename: str
    page_number: int
    snippet: str = Field(max_length=300)


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
