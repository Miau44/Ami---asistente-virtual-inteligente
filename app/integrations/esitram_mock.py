"""Implementacion mock de e-SITRAM (Sistema de Tramites Municipales) con datos de ejemplo.

Se activa con ESITRAM_MODE=mock en .env. Simula latencia minima y responde con datos
deterministicos para poder hacer demos sin credenciales reales.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.integrations.base import MunicipalAPIClient

_ESTADOS_DEMO = ["en_revision", "observado", "aprobado"]

_REQUISITOS_POR_TIPO: dict[str, list[str]] = {
    "licencia_funcionamiento": [
        "Cedula de identidad vigente",
        "NIT valido",
        "Formulario de declaracion jurada de actividad economica",
        "Croquis de ubicacion del local",
    ],
    "registro_catastral": [
        "Testimonio de propiedad",
        "Formulario RUAT actualizado",
        "Plano aprobado del inmueble",
    ],
}


class ESitramMockClient(MunicipalAPIClient):
    """Cliente simulado de e-SITRAM para desarrollo y demos."""

    async def consultar_estado_tramite(self, codigo_externo: str) -> dict[str, Any]:
        indice = sum(ord(c) for c in codigo_externo) % len(_ESTADOS_DEMO)
        return {
            "codigo_externo": codigo_externo,
            "estado": _ESTADOS_DEMO[indice],
            "observaciones": "Datos de demostracion (modo mock).",
        }

    async def iniciar_tramite(self, tipo_tramite: str, datos: dict[str, Any]) -> dict[str, Any]:
        codigo = f"ESITRAM-MOCK-{uuid.uuid4().hex[:8].upper()}"
        return {"codigo_externo": codigo, "estado": "iniciado"}

    async def listar_requisitos(self, tipo_tramite: str) -> list[str]:
        return _REQUISITOS_POR_TIPO.get(
            tipo_tramite, ["Cedula de identidad vigente", "Formulario de solicitud"]
        )
