"""Modelo ORM: documentos_validados.

IMPORTANTE: por diseno, nunca se persiste la foto/archivo del documento (ver
docs/decisiones-tecnicas.md, ADR sobre procesamiento en memoria). Solo se guarda el
resultado de la validacion y metadatos.
"""

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
    from app.db.models.tramite import Tramite


class ResultadoValidacion(enum.StrEnum):
    APROBADO = "aprobado"
    OBSERVADO = "observado"
    RECHAZADO = "rechazado"


class DocumentoValidado(TimestampMixin, Base):
    """Resultado de validar por vision una foto de documento. No almacena la imagen."""

    __tablename__ = "documentos_validados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tramite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tramites.id", ondelete="CASCADE"), nullable=False
    )
    tipo_documento: Mapped[str] = mapped_column(String(120), nullable=False)
    resultado: Mapped[ResultadoValidacion] = mapped_column(
        Enum(
            ResultadoValidacion,
            name="resultado_validacion",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    observaciones: Mapped[dict[str, object]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )

    tramite: Mapped[Tramite] = relationship(back_populates="documentos_validados")

    def __repr__(self) -> str:
        return f"<DocumentoValidado id={self.id} resultado={self.resultado}>"
