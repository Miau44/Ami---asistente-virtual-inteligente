"""Tool: search_regulations (buscar_normativa). RAG sobre normativa oficial del GAMLP.

Esta tool es el unico canal por el que el agente puede afirmar algo sobre requisitos,
montos o plazos oficiales (ver app/agents/prompts.py, regla 1). Si no encuentra
contexto relevante por encima del umbral de similitud, devuelve encontrado=false y
CERO fragmentos: el orquestador no tiene de donde inventar."""

from __future__ import annotations

from typing import Any

from app.agents.tools.registry import tool_registry
from app.services.rag_service import RagService

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "consulta": {
            "type": "string",
            "description": "Pregunta o tema a buscar en la normativa municipal oficial.",
        }
    },
    "required": ["consulta"],
}


@tool_registry.register(
    name="buscar_normativa",
    description=(
        "Busca en la normativa municipal oficial del GAMLP (ordenanzas, reglamentos) "
        "fragmentos relevantes para responder sobre requisitos, montos o plazos de un "
        "tramite. Devuelve encontrado=false si no hay informacion oficial suficientemente "
        "relevante; en ese caso NO se debe afirmar nada sobre el tema."
    ),
    input_schema=_INPUT_SCHEMA,
)
async def buscar_normativa(tool_input: dict[str, Any]) -> dict[str, Any]:
    consulta = str(tool_input["consulta"])
    rag_service = RagService()
    fragmentos = rag_service.buscar(consulta)

    if not fragmentos:
        return {
            "encontrado": False,
            "fragmentos": [],
            "mensaje": "No se encontro informacion oficial relevante para esta consulta.",
        }

    return {
        "encontrado": True,
        "fragmentos": [
            {
                "texto": f["texto"],
                "similitud": round(f["similitud"], 3),
                "fuente": {
                    "titulo": f["metadata"].get("titulo", ""),
                    "numero_norma": f["metadata"].get("numero_norma") or None,
                    "fecha_vigencia": f["metadata"].get("fecha_vigencia", ""),
                    "url_fuente": f["metadata"].get("url_fuente") or None,
                },
            }
            for f in fragmentos
        ],
    }
