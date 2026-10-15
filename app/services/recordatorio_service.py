"""Logica de negocio para recordatorios proactivos.

El idempotency_key garantiza que, aunque el worker de proactividad corra dos veces
sobre el mismo evento (ej. reintento tras un crash), no se cree ni se envie un
recordatorio duplicado."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recordatorio import EstadoRecordatorio, Recordatorio


class RecordatorioService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def crear_si_no_existe(
        self,
        ciudadano_id: uuid.UUID,
        idempotency_key: str,
        mensaje: str,
        fecha_programada: datetime,
        tramite_id: uuid.UUID | None = None,
    ) -> Recordatorio | None:
        """Inserta el recordatorio solo si idempotency_key no existe. Devuelve None si
        ya existia (evita duplicados en reintentos del worker)."""
        stmt = (
            pg_insert(Recordatorio)
            .values(
                ciudadano_id=ciudadano_id,
                tramite_id=tramite_id,
                idempotency_key=idempotency_key,
                mensaje=mensaje,
                fecha_programada=fecha_programada,
                estado=EstadoRecordatorio.PENDIENTE,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(Recordatorio)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.scalar_one_or_none()
        return row

    async def listar_pendientes_vencidos(self, ahora: datetime) -> list[Recordatorio]:
        result = await self._session.execute(
            select(Recordatorio).where(
                Recordatorio.estado == EstadoRecordatorio.PENDIENTE,
                Recordatorio.fecha_programada <= ahora,
            )
        )
        return list(result.scalars().all())

    async def marcar_enviado(self, recordatorio_id: uuid.UUID) -> None:
        recordatorio = await self._session.get(Recordatorio, recordatorio_id)
        if recordatorio is not None and recordatorio.estado == EstadoRecordatorio.PENDIENTE:
            recordatorio.estado = EstadoRecordatorio.ENVIADO
            await self._session.commit()
