"""Liveness endpoint used by the docker-compose healthcheck."""
from fastapi import APIRouter

from app.domain.schemas import HealthStatus

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(status="healthy")
