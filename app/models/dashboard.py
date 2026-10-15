"""Schemas del dashboard administrativo (endpoints agregados) y autenticacion JWT."""

from __future__ import annotations

from pydantic import Field

from app.models.common import ApiModel


class LoginRequest(ApiModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)


class TokenResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(ApiModel):
    refresh_token: str


class ResumenDashboard(ApiModel):
    total_ciudadanos: int
    total_tramites: int
    tramites_por_estado: dict[str, int]
    documentos_validados_ultimos_7_dias: int
    recordatorios_pendientes: int
