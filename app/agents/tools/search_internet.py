"""Tool: search_internet (buscar_en_internet). Busqueda web real (Tavily) para
complementar buscar_normativa cuando no hay normativa ingerida localmente sobre un
tema o rubro especifico (ver ADR-011 en docs/decisiones-tecnicas.md).

A diferencia de buscar_normativa, esto NO es una fuente oficial verificada del GAMLP:
el agente debe citar la URL y aclarar la procedencia (ver app/agents/prompts.py,
regla 2)."""

from __future__ import annotations

from typing import Any

from app.agents.tools.registry import tool_registry
from app.services.internet_search_service import InternetSearchService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "consulta": {
            "type": "string",
            "description": (
                "Que buscar en internet. Incluir siempre contexto boliviano/de La Paz "
                "explicito en la consulta (ej. 'requisitos NIT Bolivia', 'licencia de "
                "funcionamiento GAMLP venta de electrodomesticos')."
            ),
        }
    },
    "required": ["consulta"],
}


@tool_registry.register(
    name="buscar_en_internet",
    description=(
        "Busca informacion real en internet cuando buscar_normativa no encuentra nada "
        "relevante en la base de normativa oficial ingerida. Util para tramites de "
        "otras entidades (ej. SIN/NIT) o rubros especificos aun no cubiertos "
        "localmente. Los resultados NO son normativa oficial verificada del GAMLP: "
        "citar siempre la fuente/URL y aclarar que conviene confirmarlo en un canal "
        "oficial antes de que el ciudadano actue solo con base en esto."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def buscar_en_internet(tool_input: dict[str, Any]) -> dict[str, Any]:
    consulta = str(tool_input["consulta"])
    service = InternetSearchService()
    return await service.buscar(consulta)
