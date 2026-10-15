"""Tool: schedule_reminder (programar_recordatorio).

Permite al agente programar un seguimiento proactivo (ej. "avisame en 5 dias si no
hay respuesta") sin esperar a que el ciudadano vuelva a preguntar. El motor de
proactividad (app/workers/proactive_engine.py) es quien efectivamente los envia."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.agents.tools.registry import tool_registry
from app.db.session import AsyncSessionLocal
from app.services.recordatorio_service import RecordatorioService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ciudadano_id": {"type": "string", "description": "UUID del ciudadano."},
        "tramite_id": {
            "type": "string",
            "description": "UUID del tramite relacionado, si aplica.",
        },
        "mensaje": {
            "type": "string",
            "description": "Texto del recordatorio que se enviara al ciudadano por WhatsApp.",
        },
        "fecha_programada_iso": {
            "type": "string",
            "description": "Fecha y hora ISO 8601 en la que debe enviarse el recordatorio.",
        },
    },
    "required": ["ciudadano_id", "mensaje", "fecha_programada_iso"],
}


@tool_registry.register(
    name="programar_recordatorio",
    description=(
        "Programa un recordatorio proactivo para el ciudadano (ej. vencimiento de un "
        "plazo, seguimiento de un tramite). Es idempotente: si se llama dos veces con el "
        "mismo tramite y fecha no se duplica."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def programar_recordatorio(tool_input: dict[str, Any]) -> dict[str, Any]:
    try:
        ciudadano_id = uuid.UUID(str(tool_input["ciudadano_id"]))
        tramite_id = (
            uuid.UUID(str(tool_input["tramite_id"])) if tool_input.get("tramite_id") else None
        )
        fecha_programada = datetime.fromisoformat(str(tool_input["fecha_programada_iso"]))
    except ValueError as exc:
        return {"error": f"Parametros invalidos: {exc}"}

    mensaje = str(tool_input["mensaje"])
    idempotency_key = f"{ciudadano_id}:{tramite_id}:{fecha_programada.isoformat()}"

    async with AsyncSessionLocal() as session:
        service = RecordatorioService(session)
        creado = await service.crear_si_no_existe(
            ciudadano_id=ciudadano_id,
            idempotency_key=idempotency_key,
            mensaje=mensaje,
            fecha_programada=fecha_programada,
            tramite_id=tramite_id,
        )

    if creado is None:
        return {"programado": False, "mensaje": "Ya existia un recordatorio identico."}

    return {"programado": True, "recordatorio_id": str(creado.id)}
