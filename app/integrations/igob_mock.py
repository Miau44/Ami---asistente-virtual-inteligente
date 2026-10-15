"""Implementacion mock de iGOB con datos de ejemplo. Se activa con IGOB_MODE=mock."""

from __future__ import annotations

import uuid
from typing import Any

from app.integrations.base import MunicipalAPIClient

_REQUISITOS_POR_TIPO: dict[str, list[str]] = {
    "permiso_construccion": [
        "Plano arquitectonico firmado por profesional habilitado",
        "Testimonio de propiedad",
        "Boleta de pago de aranceles",
    ],
}


class IgobMockClient(MunicipalAPIClient):
    """Cliente simulado de iGOB para desarrollo y demos."""

    async def consultar_estado_tramite(self, codigo_externo: str) -> dict[str, Any]:
        return {
            "codigo_externo": codigo_externo,
            "estado": "en_revision",
            "observaciones": "Datos de demostracion (modo mock).",
        }

    async def iniciar_tramite(self, tipo_tramite: str, datos: dict[str, Any]) -> dict[str, Any]:
        codigo = f"IGOB-MOCK-{uuid.uuid4().hex[:8].upper()}"
        return {"codigo_externo": codigo, "estado": "iniciado"}

    async def listar_requisitos(self, tipo_tramite: str) -> list[str]:
        return _REQUISITOS_POR_TIPO.get(tipo_tramite, ["Formulario de solicitud iGOB"])
