"""Tool: start_procedure (iniciar_tramite).

Inicia un tramite municipal nuevo para el ciudadano (dispara iniciar_tramite en
e-SITRAM o iGOB, mock por defecto) y devuelve el tramite_id interno (UUID) que el
resto de las tools (validar_documento, consultar_estado_tramite,
programar_recordatorio) necesitan para operar sobre este mismo tramite en turnos
futuros de la conversacion."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.tools.registry import tool_registry
from app.db.session import AsyncSessionLocal
from app.integrations.factory import get_esitram_client, get_igob_client
from app.services.tramite_service import TramiteService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ciudadano_id": {
            "type": "string",
            "description": "UUID del ciudadano (viene del contexto interno de la conversacion).",
        },
        "tipo_tramite": {
            "type": "string",
            "description": (
                "Tipo de tramite, ej. 'licencia_funcionamiento', 'catastro', "
                "'patente_municipal', 'permiso_construccion'."
            ),
        },
        "sistema_origen": {
            "type": "string",
            "description": "Sistema municipal que gestiona este tramite: 'esitram' o 'igob'.",
        },
        "actividad_economica": {
            "type": "string",
            "description": "Actividad economica del negocio, si aplica.",
        },
        "nombre_comercial": {
            "type": "string",
            "description": "Nombre comercial del negocio, si aplica.",
        },
        "direccion": {
            "type": "string",
            "description": "Direccion del local o predio, si aplica.",
        },
    },
    "required": ["ciudadano_id", "tipo_tramite", "sistema_origen"],
}


@tool_registry.register(
    name="iniciar_tramite",
    description=(
        "Inicia un tramite municipal nuevo para el ciudadano cuando ya se junto la "
        "informacion minima necesaria (tipo de tramite y datos basicos del negocio o "
        "predio). Devuelve un tramite_id que se debe usar en tools posteriores "
        "(validar_documento, consultar_estado_tramite, programar_recordatorio) para "
        "este mismo tramite. No llamar sin haber entendido primero que necesita el "
        "ciudadano."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def iniciar_tramite(tool_input: dict[str, Any]) -> dict[str, Any]:
    try:
        ciudadano_id = uuid.UUID(str(tool_input["ciudadano_id"]))
    except ValueError:
        return {"error": "ciudadano_id invalido"}

    tipo_tramite = str(tool_input["tipo_tramite"])
    sistema_origen = str(tool_input.get("sistema_origen") or "esitram")
    metadata_tramite = {
        key: str(tool_input[key])
        for key in ("actividad_economica", "nombre_comercial", "direccion")
        if tool_input.get(key)
    }

    cliente = get_esitram_client() if sistema_origen == "esitram" else get_igob_client()

    async with AsyncSessionLocal() as session:
        service = TramiteService(session, cliente)
        tramite = await service.crear(
            ciudadano_id=ciudadano_id,
            tipo_tramite=tipo_tramite,
            sistema_origen=sistema_origen,
            metadata_tramite=metadata_tramite,
        )

    return {
        "tramite_id": str(tramite.id),
        "codigo_externo": tramite.codigo_externo,
        "estado": tramite.estado.value,
    }
