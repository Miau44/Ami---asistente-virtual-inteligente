"""POST /api/v1/documentos/validar - validacion de documentos por foto (vision).

La imagen se procesa en memoria y se descarta despues del analisis; nunca se guarda
en disco ni se pasa a servicios que la persistan (ver docs/decisiones-tecnicas.md)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.v1.deps import rate_limiter
from app.core.exceptions import DocumentValidationError
from app.models.documento import ValidarDocumentoResponse
from app.services.documento_service import DocumentoService

router = APIRouter(prefix="/documentos", tags=["documentos"])

_MAX_TAMANO_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post(
    "/validar",
    response_model=ValidarDocumentoResponse,
    dependencies=[Depends(rate_limiter(scope="documentos_validar", limit_per_minute=20))],
)
async def validar_documento(
    tramite_id: Annotated[uuid.UUID, Form()],
    tipo_documento: Annotated[str, Form(min_length=2, max_length=120)],
    archivo: Annotated[UploadFile, File()],
) -> ValidarDocumentoResponse:
    contenido = await archivo.read()
    if len(contenido) > _MAX_TAMANO_BYTES:
        raise DocumentValidationError("La imagen supera el tamano maximo permitido (8 MB).")

    media_type = archivo.content_type or "image/jpeg"
    service = DocumentoService()
    try:
        documento = await service.validar(tramite_id, tipo_documento, contenido, media_type)
    finally:
        contenido = b""  # descartar explicitamente la referencia a los bytes de la imagen

    return ValidarDocumentoResponse.model_validate(documento)
