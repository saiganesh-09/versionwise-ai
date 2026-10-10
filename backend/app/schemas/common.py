"""Shared response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessCheck(BaseModel):
    name: str
    status: str  # "ok" | "unavailable"
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str  # "ready" | "degraded"
    checks: list[ReadinessCheck]
