"""Schemas del dominio tramites."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.db.models.tramite import EstadoTramite
from app.models.common import ApiModel


class TramiteResponse(ApiModel):
    id: uuid.UUID
    ciudadano_id: uuid.UUID
    tipo_tramite: str
    sistema_origen: str
    codigo_externo: str | None
    estado: EstadoTramite
    metadata_tramite: dict[str, object]
    created_at: datetime
    updated_at: datetime


class TramiteCreateRequest(ApiModel):
    ciudadano_id: uuid.UUID
    tipo_tramite: str = Field(..., min_length=2, max_length=120)
    sistema_origen: str = Field(..., min_length=2, max_length=50)
    metadata_tramite: dict[str, object] = Field(default_factory=dict)
