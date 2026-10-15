"""Logica de negocio para tramites: iniciar, consultar estado, sincronizar con
sistemas municipales via la interfaz MunicipalAPIClient (mock o real)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.tramite import EstadoTramite, Tramite
from app.integrations.base import MunicipalAPIClient

_ESTADOS_EXTERNOS_VALIDOS = {e.value for e in EstadoTramite}


class TramiteService:
    def __init__(self, session: AsyncSession, cliente_municipal: MunicipalAPIClient) -> None:
        self._session = session
        self._cliente = cliente_municipal

    async def obtener(self, tramite_id: uuid.UUID) -> Tramite:
        tramite = await self._session.get(Tramite, tramite_id)
        if tramite is None:
            raise NotFoundError(f"Tramite {tramite_id} no encontrado")
        return tramite

    async def listar_por_ciudadano(self, ciudadano_id: uuid.UUID) -> list[Tramite]:
        result = await self._session.execute(
            select(Tramite).where(Tramite.ciudadano_id == ciudadano_id)
        )
        return list(result.scalars().all())

    async def buscar_por_codigo_externo(self, codigo_externo: str) -> Tramite | None:
        """Busca un tramite por su codigo de seguimiento (el que conoce el ciudadano,
        ej. "ESITRAM-MOCK-XXXX"), para funcionarios que no tienen a mano el UUID
        interno del tramite/ciudadano."""
        result = await self._session.execute(
            select(Tramite).where(Tramite.codigo_externo == codigo_externo)
        )
        return result.scalar_one_or_none()

    async def crear(
        self,
        ciudadano_id: uuid.UUID,
        tipo_tramite: str,
        sistema_origen: str,
        metadata_tramite: dict[str, Any],
    ) -> Tramite:
        externo = await self._cliente.iniciar_tramite(tipo_tramite, metadata_tramite)
        tramite = Tramite(
            ciudadano_id=ciudadano_id,
            tipo_tramite=tipo_tramite,
            sistema_origen=sistema_origen,
            codigo_externo=externo.get("codigo_externo"),
            estado=EstadoTramite.INICIADO,
            metadata_tramite=metadata_tramite,
        )
        self._session.add(tramite)
        await self._session.commit()
        await self._session.refresh(tramite)
        return tramite

    async def sincronizar_estado(self, tramite_id: uuid.UUID) -> Tramite:
        """Consulta el estado actual en el sistema municipal y actualiza el registro local.

        Si MunicipalAPIClient lanza MunicipalAPIUnavailableError, se propaga: el
        llamador (tool del agente / endpoint) decide como degradar."""
        tramite = await self.obtener(tramite_id)
        if not tramite.codigo_externo:
            return tramite

        externo = await self._cliente.consultar_estado_tramite(tramite.codigo_externo)
        nuevo_estado = externo.get("estado")
        if isinstance(nuevo_estado, str) and nuevo_estado in _ESTADOS_EXTERNOS_VALIDOS:
            tramite.estado = EstadoTramite(nuevo_estado)
            await self._session.commit()
            await self._session.refresh(tramite)
        return tramite
