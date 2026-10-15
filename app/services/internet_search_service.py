"""Servicio de busqueda web real (Tavily) para complementar el RAG de normativa
oficial cuando no hay contenido ingerido localmente sobre un tema especifico.

A diferencia de RagService, esto NO es una fuente oficial verificada del GAMLP: los
resultados vienen de la web abierta. El agente esta instruido (ver
app/agents/prompts.py, regla 2) para dejar explicito que es informacion de internet,
no normativa oficial confirmada, y sugerir verificarla en un canal oficial antes de
que el ciudadano actue solo con base en eso. Ver ADR-011 en
docs/decisiones-tecnicas.md."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class InternetSearchService:
    """Busca en internet via Tavily. Nunca lanza: cualquier fallo se traduce en
    `encontrado=False` para que el agente admita honestamente que no encontro nada,
    igual que RagService ante una busqueda de normativa sin resultados relevantes."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.TAVILY_API_KEY
        self._max_results = settings.TAVILY_MAX_RESULTS

    async def buscar(self, consulta: str) -> dict[str, Any]:
        if not self._api_key:
            return _sin_resultados("La busqueda en internet no esta configurada.")

        payload = {
            "api_key": self._api_key,
            "query": consulta,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": self._max_results,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(_TAVILY_URL, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("internet_search_failed", error_type=type(exc).__name__)
            return _sin_resultados("No se pudo completar la busqueda en internet en este momento.")

        resultados = data.get("results") or []
        if not resultados:
            return _sin_resultados(
                "No se encontro informacion relevante en internet para esta consulta."
            )

        return {
            "encontrado": True,
            "resumen": data.get("answer"),
            "resultados": [
                {
                    "titulo": r.get("title", ""),
                    "url": r.get("url", ""),
                    "extracto": (r.get("content") or "")[:500],
                }
                for r in resultados
            ],
        }


def _sin_resultados(mensaje: str) -> dict[str, Any]:
    return {"encontrado": False, "resultados": [], "mensaje": mensaje}
