"""Tool: list_citizen_procedures (listar_tramites_ciudadano).

Le permite al agente recuperar el/los tramite_id de un ciudadano en cualquier turno
de la conversacion (incluso en un mensaje nuevo de un dia distinto, sin tener que
"recordarlo" de un turno anterior) — necesario antes de llamar validar_documento,
consultar_estado_tramite o programar_recordatorio si el tramite_id no esta ya claro
en el contexto reciente de la conversacion."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.tools.registry import tool_registry
from app.db.session import AsyncSessionLocal
from app.integrations.factory import get_esitram_client
from app.services.tramite_service import TramiteService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ciudadano_id": {
            "type": "string",
            "description": "UUID del ciudadano (viene del contexto interno de la conversacion).",
        },
    },
    "required": ["ciudadano_id"],
}


@tool_registry.register(
    name="listar_tramites_ciudadano",
    description=(
        "Lista los tramites que el ciudadano ya tiene registrados (tramite_id, tipo, "
        "estado y codigo externo de cada uno). Usar esto para recuperar el tramite_id "
        "correcto antes de validar_documento, consultar_estado_tramite o "
        "programar_recordatorio, si no esta ya claro en la conversacion reciente cual "
        "es. Si devuelve una lista vacia, el ciudadano todavia no tiene ningun tramite "
        "iniciado."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def listar_tramites_ciudadano(tool_input: dict[str, Any]) -> dict[str, Any]:
    try:
        ciudadano_id = uuid.UUID(str(tool_input["ciudadano_id"]))
    except ValueError:
        return {"error": "ciudadano_id invalido"}

    async with AsyncSessionLocal() as session:
        service = TramiteService(session, get_esitram_client())
        tramites = await service.listar_por_ciudadano(ciudadano_id)

    return {
        "tramites": [
            {
                "tramite_id": str(t.id),
                "tipo_tramite": t.tipo_tramite,
                "estado": t.estado.value,
                "codigo_externo": t.codigo_externo,
            }
            for t in tramites
        ]
    }
