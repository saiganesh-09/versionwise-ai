"""Public (non-secret) runtime configuration — for the Settings page."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public")
def public_settings(
    current: CurrentUser, settings: Settings = Depends(get_settings)
) -> dict:
    """Provider/model/limit names only — never keys or URLs containing secrets."""
    return {
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "object_storage_provider": settings.object_storage_provider,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "retrieval_top_k": settings.retrieval_top_k,
        "retrieval_similarity_threshold": settings.retrieval_similarity_threshold,
        "max_upload_mb": settings.max_upload_mb,
        "access_token_expire_minutes": settings.access_token_expire_minutes,
    }
