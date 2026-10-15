"""Modelo ORM: recordatorios (usado por el motor de proactividad)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.ciudadano import Ciudadano
    from app.db.models.tramite import Tramite


class EstadoRecordatorio(enum.StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    CANCELADO = "cancelado"


class Recordatorio(TimestampMixin, Base):
    """Un recordatorio proactivo (vencimiento, cambio de estado) para un ciudadano.

    idempotency_key evita que el worker envie el mismo aviso dos veces si corre
    en paralelo o se reintenta sobre el mismo evento.
    """

    __tablename__ = "recordatorios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ciudadano_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ciudadanos.id", ondelete="CASCADE"), nullable=False
    )
    tramite_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tramites.id", ondelete="CASCADE"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    mensaje: Mapped[str] = mapped_column(String(1000), nullable=False)
    fecha_programada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[EstadoRecordatorio] = mapped_column(
        Enum(
            EstadoRecordatorio,
            name="estado_recordatorio",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=EstadoRecordatorio.PENDIENTE,
        nullable=False,
    )

    ciudadano: Mapped[Ciudadano] = relationship(back_populates="recordatorios")
    tramite: Mapped[Tramite | None] = relationship(back_populates="recordatorios")

    def __repr__(self) -> str:
        return f"<Recordatorio id={self.id} estado={self.estado}>"
