"""Tool: check_procedure_status (consultar_estado_tramite).

Consulta el estado de un tramite contra el sistema municipal correspondiente
(e-SITRAM o iGOB, mock o real segun configuracion). Si el sistema no responde,
degrada elegantemente en vez de propagar un error crudo al ciudadano."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.tools.registry import tool_registry
from app.core.exceptions import MunicipalAPIUnavailableError, NotFoundError
from app.db.models.tramite import Tramite
from app.db.session import AsyncSessionLocal
from app.integrations.factory import get_esitram_client, get_igob_client
from app.services.tramite_service import TramiteService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tramite_id": {
            "type": "string",
            "description": "UUID del tramite a consultar (id interno de AMI Copiloto).",
        }
    },
    "required": ["tramite_id"],
}


@tool_registry.register(
    name="consultar_estado_tramite",
    description=(
        "Consulta el estado actual de un tramite del ciudadano contra el sistema "
        "municipal correspondiente (e-SITRAM o iGOB). Usar cuando el ciudadano "
        "pregunta 'en que va mi tramite' o similar."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def consultar_estado_tramite(tool_input: dict[str, Any]) -> dict[str, Any]:
    try:
        tramite_id = uuid.UUID(str(tool_input["tramite_id"]))
    except ValueError:
        return {"error": "tramite_id invalido"}

    async with AsyncSessionLocal() as session:
        try:
            tramite_previo = await session.get(Tramite, tramite_id)
            if tramite_previo is None:
                raise NotFoundError("Tramite no encontrado")

            cliente = (
                get_esitram_client()
                if tramite_previo.sistema_origen == "esitram"
                else get_igob_client()
            )
            service = TramiteService(session, cliente)
            tramite = await service.sincronizar_estado(tramite_id)
            return {
                "disponible": True,
                "tramite_id": str(tramite.id),
                "tipo_tramite": tramite.tipo_tramite,
                "estado": tramite.estado.value,
                "codigo_externo": tramite.codigo_externo,
            }
        except NotFoundError:
            return {"disponible": False, "error": "Tramite no encontrado"}
        except MunicipalAPIUnavailableError:
            return {
                "disponible": False,
                "degradado": True,
                "mensaje": (
                    "No puedo verificar el estado del tramite en este momento porque el "
                    "sistema municipal no responde. Intenta de nuevo en unos minutos."
                ),
            }
