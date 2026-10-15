"""Test critico de seguridad (requisito #8): si el RAG no encuentra contexto relevante
por encima del umbral de similitud, la tool buscar_normativa DEBE devolver
encontrado=false y CERO fragmentos, para que el agente nunca tenga de donde inventar
requisitos o montos. Ver app/agents/prompts.py (regla 1) y app/services/rag_service.py.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.tools.search_regulations import buscar_normativa


@pytest.mark.asyncio
async def test_buscar_normativa_sin_resultados_relevantes_no_alucina() -> None:
    with patch("app.agents.tools.search_regulations.RagService") as MockRagService:
        MockRagService.return_value.buscar.return_value = []

        resultado = await buscar_normativa({"consulta": "requisitos para viajar a la luna"})

    assert resultado["encontrado"] is False
    assert resultado["fragmentos"] == []
    assert "mensaje" in resultado


@pytest.mark.asyncio
async def test_buscar_normativa_con_resultados_relevantes_incluye_fuente_y_fecha() -> None:
    with patch("app.agents.tools.search_regulations.RagService") as MockRagService:
        MockRagService.return_value.buscar.return_value = [
            {
                "texto": "Se requiere licencia de funcionamiento vigente.",
                "similitud": 0.82,
                "metadata": {
                    "titulo": "Ordenanza Municipal 123/2024",
                    "numero_norma": "OM 123/2024",
                    "fecha_vigencia": "2024-01-15",
                    "url_fuente": "https://lapaz.bo/normativa/123",
                },
            }
        ]

        resultado = await buscar_normativa({"consulta": "requisitos licencia de funcionamiento"})

    assert resultado["encontrado"] is True
    fragmento = resultado["fragmentos"][0]
    assert fragmento["fuente"]["titulo"] == "Ordenanza Municipal 123/2024"
    assert fragmento["fuente"]["fecha_vigencia"] == "2024-01-15"
