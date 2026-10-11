"""Conflict + comparison schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DetectRequest(BaseModel):
    document_id: uuid.UUID | None = None  # scope detection to one document


class ConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID | None
    chunk_a_id: uuid.UUID | None
    chunk_b_id: uuid.UUID | None
    conflict_type: str
    explanation: str
    evidence_a: str
    evidence_b: str
    confidence: float | None
    status: str
    resolution_note: str | None
    reviewed_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DetectResponse(BaseModel):
    candidates_evaluated: int
    findings: list[ConflictOut]


class ReviewRequest(BaseModel):
    action: Literal["confirm", "dismiss", "resolve"]
    note: str | None = Field(default=None, max_length=2000)


class DiffLine(BaseModel):
    op: Literal["added", "removed", "same"]
    text: str


class CompareResponse(BaseModel):
    version_a: dict
    version_b: dict
    added: list[str]
    removed: list[str]
    changed_hint: bool  # True when the two revisions actually differ
