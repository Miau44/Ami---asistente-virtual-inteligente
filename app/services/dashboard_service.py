"""Agregaciones para el dashboard administrativo consumido por el equipo de frontend."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ciudadano import Ciudadano
from app.db.models.documento_validado import DocumentoValidado
from app.db.models.recordatorio import EstadoRecordatorio, Recordatorio
from app.db.models.tramite import Tramite


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resumen(self) -> dict[str, object]:
        total_ciudadanos = (
            await self._session.execute(select(func.count()).select_from(Ciudadano))
        ).scalar_one()
        total_tramites = (
            await self._session.execute(select(func.count()).select_from(Tramite))
        ).scalar_one()

        por_estado_rows = (
            await self._session.execute(
                select(Tramite.estado, func.count()).group_by(Tramite.estado)
            )
        ).all()
        tramites_por_estado = {estado.value: count for estado, count in por_estado_rows}

        hace_7_dias = datetime.now(UTC) - timedelta(days=7)
        documentos_recientes = (
            await self._session.execute(
                select(func.count())
                .select_from(DocumentoValidado)
                .where(DocumentoValidado.created_at >= hace_7_dias)
            )
        ).scalar_one()

        recordatorios_pendientes = (
            await self._session.execute(
                select(func.count())
                .select_from(Recordatorio)
                .where(Recordatorio.estado == EstadoRecordatorio.PENDIENTE)
            )
        ).scalar_one()

        return {
            "total_ciudadanos": total_ciudadanos,
            "total_tramites": total_tramites,
            "tramites_por_estado": tramites_por_estado,
            "documentos_validados_ultimos_7_dias": documentos_recientes,
            "recordatorios_pendientes": recordatorios_pendientes,
        }
