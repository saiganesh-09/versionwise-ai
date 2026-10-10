"""Enumerations shared across models.

Backed by native Postgres ENUM types. `str` mix-in keeps values JSON-friendly
and usable as plain strings in the application layer.
"""

import enum


class UserRole(enum.StrEnum):
    user = "user"
    document_manager = "document_manager"
    admin = "admin"


class VersionStatus(enum.StrEnum):
    """Lifecycle of a document version.

    draft          — uploaded, content editable/incomplete
    pending_review — submitted for approval
    approved       — authoritative for retrieval when its interval applies
    superseded     — replaced by a newer approved version; still retrievable
                     for historical queries
    archived       — withdrawn from retrieval entirely
    """

    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    superseded = "superseded"
    archived = "archived"


class IngestionStatus(enum.StrEnum):
    """Separate from version lifecycle: a version is retrieval-eligible only
    when status=approved AND ingestion_status=completed."""

    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentPermission(enum.StrEnum):
    read = "read"
    write = "write"
    manage = "manage"


class ConflictType(enum.StrEnum):
    consistent = "consistent"
    contradictory = "contradictory"
    updated_by_newer_version = "updated_by_newer_version"
    context_dependent = "context_dependent"
    insufficient_evidence = "insufficient_evidence"


class ConflictStatus(enum.StrEnum):
    potential = "potential"
    confirmed = "confirmed"
    dismissed = "dismissed"
    resolved = "resolved"


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"
