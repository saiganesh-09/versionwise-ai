"""Aggregated /api/v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, chat, conflicts, documents, health, versions

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(versions.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(conflicts.router)
