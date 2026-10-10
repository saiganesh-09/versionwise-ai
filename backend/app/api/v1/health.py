"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.db.session import check_database
from app.schemas.common import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness probe — the process is up and serving."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    """Readiness probe — reports whether dependencies are reachable.

    Returns 503 when degraded so orchestrators can gate traffic.
    """
    db_ok, db_detail = check_database()
    checks = [
        ReadinessCheck(name="database", status="ok" if db_ok else "unavailable", detail=db_detail)
    ]
    ready = all(c.status == "ok" for c in checks)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if ready else "degraded", checks=checks)
