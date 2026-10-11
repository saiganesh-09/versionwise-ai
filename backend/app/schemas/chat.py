"""Chat request/response schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None  # scope the question to one document
    as_of_date: date | None = None        # explicit override of parsed intent


class CitationOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    version_id: str
    version_number: int
    effective_from: str
    effective_until: str | None
    page_number: int | None
    section_title: str | None
    content: str
    score: float
    rank: int


class TemporalIntentOut(BaseModel):
    kind: str
    as_of: str | None
    compare_a: str | None
    compare_b: str | None
    ambiguous: bool
    resolved_by: str


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID
    status: str  # answered | insufficient_evidence
    answer: str
    citations: list[CitationOut]
    evidence: list[CitationOut]  # everything retrieved, cited or not
    warnings: list[str]
    intent: TemporalIntentOut


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    as_of_date: date | None
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class SessionDetailOut(SessionOut):
    messages: list[MessageOut] = []
