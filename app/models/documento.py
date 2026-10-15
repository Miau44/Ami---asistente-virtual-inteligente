"""Schemas del dominio validacion de documentos."""

from __future__ import annotations

import uuid

from pydantic import Field

from app.db.models.documento_validado import ResultadoValidacion
from app.models.common import ApiModel


class ValidarDocumentoRequest(ApiModel):
    tramite_id: uuid.UUID
    tipo_documento: str = Field(..., min_length=2, max_length=120)
    # La imagen llega como multipart/form-data (UploadFile), no como parte de este JSON;
    # este schema documenta los metadatos que acompanan al archivo.


class ValidarDocumentoResponse(ApiModel):
    tramite_id: uuid.UUID
    tipo_documento: str
    resultado: ResultadoValidacion
    observaciones: dict[str, object]
