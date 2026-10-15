"""Interfaz abstracta para clientes de sistemas municipales.

Regla de arquitectura: la aplicacion NUNCA accede directo a bases de datos
institucionales, solo via API REST, y siempre a traves de esta interfaz. Cada
integracion (e-SITRAM, iGOB, Gestion Documental) implementa dos clases -real y mock-
que exponen exactamente los mismos metodos, seleccionadas por configuracion
(ESITRAM_MODE=mock|real, etc.) para que la capa de negocio nunca sepa cual esta activa.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MunicipalAPIClient(ABC):
    """Contrato comun para cualquier cliente de sistema municipal externo."""

    @abstractmethod
    async def consultar_estado_tramite(self, codigo_externo: str) -> dict[str, Any]:
        """Consulta el estado actual de un tramite por su codigo en el sistema externo."""

    @abstractmethod
    async def iniciar_tramite(self, tipo_tramite: str, datos: dict[str, Any]) -> dict[str, Any]:
        """Inicia un nuevo tramite en el sistema externo y devuelve su codigo/estado inicial."""

    @abstractmethod
    async def listar_requisitos(self, tipo_tramite: str) -> list[str]:
        """Lista los requisitos documentales oficiales para un tipo de tramite."""
