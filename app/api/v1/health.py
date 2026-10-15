"""GET /api/v1/health - liveness/readiness del servicio."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.common import ApiModel

router = APIRouter(tags=["health"])


class HealthResponse(ApiModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse, summary="Liveness/readiness check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ami-copiloto-backend")
