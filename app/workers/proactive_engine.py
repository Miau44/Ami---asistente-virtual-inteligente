"""Motor de proactividad: job periodico (APScheduler) que revisa recordatorios
vencidos y notifica al ciudadano por WhatsApp sin que este pregunte.

Diseno: stateless e idempotente. Cada ejecucion vuelve a consultar la base de datos
(no guarda estado en memoria entre corridas) y cada recordatorio tiene un
idempotency_key unico + se marca ENVIADO dentro de la misma operacion que dispara el
envio, de modo que si el proceso corre dos veces sobre el mismo evento (crash y
reintento, dos workers en paralelo) no se duplica la notificacion."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import MunicipalAPIUnavailableError
from app.core.logging import configure_logging, get_logger
from app.db.models.ciudadano import Ciudadano
from app.db.models.recordatorio import EstadoRecordatorio, Recordatorio
from app.db.session import AsyncSessionLocal
from app.integrations.whatsapp_client import WhatsAppClient
from app.services.recordatorio_service import RecordatorioService

logger = get_logger(__name__)


async def procesar_recordatorios_pendientes() -> int:
    """Envia los recordatorios cuya fecha_programada ya se cumplio. Devuelve cuantos
    se enviaron. Idempotente: usa UPDATE condicional (estado=PENDIENTE) al marcar
    ENVIADO antes de considerar el envio exitoso como definitivo."""
    ahora = datetime.now(UTC)
    enviados = 0
    whatsapp = WhatsAppClient()

    async with AsyncSessionLocal() as session:
        service = RecordatorioService(session)
        pendientes = await service.listar_pendientes_vencidos(ahora)

        for recordatorio in pendientes:
            # Reclamar el recordatorio de forma atomica: si otro worker ya lo tomo,
            # este UPDATE afecta 0 filas y se salta el envio (evita duplicados).
            claimed = await _reclamar_recordatorio(session, recordatorio.id)
            if not claimed:
                continue

            try:
                async with AsyncSessionLocal() as session_ciudadano:
                    ciudadano = await session_ciudadano.get(Ciudadano, recordatorio.ciudadano_id)
                if ciudadano is None:
                    continue
                await whatsapp.enviar_mensaje(ciudadano.telefono_whatsapp, recordatorio.mensaje)
                enviados += 1
                logger.info("recordatorio_enviado", recordatorio_id=str(recordatorio.id))
            except MunicipalAPIUnavailableError:
                # Revertir a PENDIENTE para reintentar en la siguiente corrida.
                await _revertir_a_pendiente(session, recordatorio.id)
                logger.warning("recordatorio_envio_fallido", recordatorio_id=str(recordatorio.id))

    return enviados


async def _reclamar_recordatorio(session: AsyncSession, recordatorio_id: uuid.UUID) -> bool:
    """UPDATE condicional PENDIENTE->ENVIADO: si otro worker ya lo reclamo, afecta 0 filas."""
    result = await session.execute(
        update(Recordatorio)
        .where(
            Recordatorio.id == recordatorio_id,
            Recordatorio.estado == EstadoRecordatorio.PENDIENTE,
        )
        .values(estado=EstadoRecordatorio.ENVIADO)
    )
    await session.commit()
    rowcount: int = result.rowcount  # type: ignore[attr-defined]
    return rowcount > 0


async def _revertir_a_pendiente(session: AsyncSession, recordatorio_id: uuid.UUID) -> None:
    await session.execute(
        update(Recordatorio)
        .where(Recordatorio.id == recordatorio_id)
        .values(estado=EstadoRecordatorio.PENDIENTE)
    )
    await session.commit()


def iniciar_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        procesar_recordatorios_pendientes,
        "interval",
        minutes=settings.PROACTIVE_ENGINE_INTERVAL_MINUTES,
        id="proactive_engine_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "proactive_engine_iniciado",
        intervalo_minutos=settings.PROACTIVE_ENGINE_INTERVAL_MINUTES,
    )
    return scheduler


async def _run_forever() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.PROACTIVE_ENGINE_ENABLED:
        logger.info("proactive_engine_deshabilitado")
        return

    iniciar_scheduler()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(_run_forever())
