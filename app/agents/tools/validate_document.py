"""Tool: validate_document (validar_documento). Valida por vision una foto de documento.

El modelo de lenguaje decide CUANDO llamar a esta tool y con que tipo_documento/tramite_id,
pero nunca genera ni ve los bytes de la imagen (seria absurdo pedirle que "escriba" una
foto). Los bytes viajan por un canal separado: el orquestador los deja en
`imagen_actual` (contextvar) antes de invocar al modelo, y esta tool los lee de ahi. La
imagen se descarta apenas termina el analisis: nunca se persiste a disco ni al vector
store (ver docs/decisiones-tecnicas.md)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from app.agents.tools.registry import tool_registry
from app.core.exceptions import DocumentValidationError
from app.services.documento_service import DocumentoService

imagen_actual: ContextVar[tuple[bytes, str] | None] = ContextVar("imagen_actual", default=None)

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tramite_id": {
            "type": "string",
            "description": "UUID del tramite al que pertenece el documento.",
        },
        "tipo_documento": {
            "type": "string",
            "description": "Tipo de documento a validar, ej. 'cedula_identidad', 'nit', 'plano'.",
        },
    },
    "required": ["tramite_id", "tipo_documento"],
}


@tool_registry.register(
    name="validar_documento",
    description=(
        "Analiza por vision la ultima foto de documento enviada por el ciudadano en la "
        "conversacion y determina si es apta para presentar en el tramite. Usar SIEMPRE "
        "antes de confirmar que un documento esta listo."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def validar_documento(tool_input: dict[str, Any]) -> dict[str, Any]:
    imagen = imagen_actual.get()
    if imagen is None:
        return {"error": "No hay ninguna foto de documento disponible para validar en este turno."}

    imagen_bytes, media_type = imagen
    try:
        tramite_id = uuid.UUID(str(tool_input["tramite_id"]))
    except ValueError:
        return {"error": "tramite_id invalido"}

    tipo_documento = str(tool_input["tipo_documento"])

    service = DocumentoService()
    try:
        documento = await service.validar(tramite_id, tipo_documento, imagen_bytes, media_type)
    except DocumentValidationError as exc:
        return {"error": exc.message}
    finally:
        imagen_actual.set(None)  # descartar la imagen del contexto tan pronto se use

    return {
        "tramite_id": str(documento.tramite_id),
        "tipo_documento": documento.tipo_documento,
        "resultado": documento.resultado.value,
        "observaciones": documento.observaciones,
    }
