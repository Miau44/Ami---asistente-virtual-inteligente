"""Modelo ORM: tramites."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import JSONVariant

if TYPE_CHECKING:
    from app.db.models.ciudadano import Ciudadano
    from app.db.models.documento_validado import DocumentoValidado
    from app.db.models.recordatorio import Recordatorio


class EstadoTramite(enum.StrEnum):
    INICIADO = "iniciado"
    EN_REVISION = "en_revision"
    OBSERVADO = "observado"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    VENCIDO = "vencido"


class Tramite(TimestampMixin, Base):
    """Un tramite municipal iniciado o en seguimiento para un ciudadano."""

    __tablename__ = "tramites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ciudadano_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ciudadanos.id", ondelete="CASCADE"), nullable=False
    )
    tipo_tramite: Mapped[str] = mapped_column(String(120), nullable=False)
    sistema_origen: Mapped[str] = mapped_column(String(50), nullable=False)  # esitram | igob
    codigo_externo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[EstadoTramite] = mapped_column(
        Enum(
            EstadoTramite,
            name="estado_tramite",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=EstadoTramite.INICIADO,
        nullable=False,
    )
    metadata_tramite: Mapped[dict[str, object]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )

    ciudadano: Mapped[Ciudadano] = relationship(back_populates="tramites")
    documentos_validados: Mapped[list[DocumentoValidado]] = relationship(back_populates="tramite")
    recordatorios: Mapped[list[Recordatorio]] = relationship(back_populates="tramite")

    def __repr__(self) -> str:
        return f"<Tramite id={self.id} tipo={self.tipo_tramite} estado={self.estado}>"
