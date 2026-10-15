"""Schemas del dominio recordatorios."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.db.models.recordatorio import EstadoRecordatorio
from app.models.common import ApiModel


class RecordatorioResponse(ApiModel):
    id: uuid.UUID
    ciudadano_id: uuid.UUID
    tramite_id: uuid.UUID | None
    mensaje: str
    fecha_programada: datetime
    estado: EstadoRecordatorio


class RecordatorioCreateRequest(ApiModel):
    ciudadano_id: uuid.UUID
    tramite_id: uuid.UUID | None = None
    mensaje: str = Field(..., min_length=3, max_length=1000)
    fecha_programada: datetime
