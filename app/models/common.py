"""Schemas compartidos entre dominios."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base para todos los schemas de la API: prohibe campos extra por defecto."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorResponse(ApiModel):
    error_code: str
    message: str


class FuenteCitada(ApiModel):
    """Fuente y fecha de vigencia de una norma citada por el agente (anti-alucinacion)."""

    titulo: str
    numero_norma: str | None = None
    fecha_vigencia: str
    url_fuente: str | None = None
