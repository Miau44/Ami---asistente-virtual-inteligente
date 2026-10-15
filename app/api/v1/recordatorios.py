"""Endpoints de recordatorios: creacion manual (uso admin) y consulta."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_admin_subject, rate_limiter
from app.db.models.recordatorio import Recordatorio
from app.db.session import get_db_session
from app.models.recordatorio import RecordatorioCreateRequest, RecordatorioResponse
from app.services.recordatorio_service import RecordatorioService

router = APIRouter(prefix="/recordatorios", tags=["recordatorios"])


@router.get(
    "",
    response_model=list[RecordatorioResponse],
    dependencies=[Depends(rate_limiter(scope="recordatorios_list", limit_per_minute=30))],
)
async def listar_recordatorios(
    ciudadano_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[RecordatorioResponse]:
    result = await session.execute(
        select(Recordatorio).where(Recordatorio.ciudadano_id == ciudadano_id)
    )
    return [RecordatorioResponse.model_validate(r) for r in result.scalars().all()]


@router.post(
    "",
    response_model=RecordatorioResponse,
    status_code=201,
    dependencies=[Depends(get_current_admin_subject)],
)
async def crear_recordatorio(
    payload: RecordatorioCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecordatorioResponse:
    service = RecordatorioService(session)
    idempotency_key = (
        f"{payload.ciudadano_id}:{payload.tramite_id}:{payload.fecha_programada.isoformat()}"
    )
    creado = await service.crear_si_no_existe(
        ciudadano_id=payload.ciudadano_id,
        idempotency_key=idempotency_key,
        mensaje=payload.mensaje,
        fecha_programada=payload.fecha_programada,
        tramite_id=payload.tramite_id,
    )
    if creado is None:
        result = await session.execute(
            select(Recordatorio).where(Recordatorio.idempotency_key == idempotency_key)
        )
        creado = result.scalar_one()

    return RecordatorioResponse.model_validate(creado)
