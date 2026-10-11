"""Document request/response schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    document_type: str = Field(default="general", max_length=100)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    document_type: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    original_filename: str
    file_hash: str
    effective_from: date
    effective_until: date | None
    status: str
    ingestion_status: str
    uploaded_by: uuid.UUID
    uploaded_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    supersedes_version_id: uuid.UUID | None
    extra: dict = {}  # ingestion stats/errors — never secrets


class VersionApproveRequest(BaseModel):
    supersede_version_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=1000)


class VersionRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ChunkResponse(BaseModel):
    """Embedding intentionally excluded — not useful to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None
    section_title: str | None
    token_count: int | None
    content_hash: str | None
    created_at: datetime


class DocumentDetailResponse(DocumentResponse):
    versions: list[DocumentVersionResponse] = []
