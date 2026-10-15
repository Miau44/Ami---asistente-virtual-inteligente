"""Schemas del dominio normativa (RAG)."""

from __future__ import annotations

from pydantic import Field

from app.models.common import ApiModel, FuenteCitada


class BusquedaNormativaRequest(ApiModel):
    consulta: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class FragmentoNormativa(ApiModel):
    texto: str
    similitud: float = Field(..., ge=0.0, le=1.0)
    fuente: FuenteCitada


class BusquedaNormativaResponse(ApiModel):
    consulta: str
    encontrado: bool
    fragmentos: list[FragmentoNormativa]
    mensaje: str | None = None
