"""Modelo ORM: ciudadanos."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversacion import Conversacion
    from app.db.models.recordatorio import Recordatorio
    from app.db.models.tramite import Tramite


class Ciudadano(TimestampMixin, Base):
    """Un ciudadano que interactua con AMI Copiloto via WhatsApp."""

    __tablename__ = "ciudadanos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telefono_whatsapp: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)

    tramites: Mapped[list[Tramite]] = relationship(back_populates="ciudadano")
    conversaciones: Mapped[list[Conversacion]] = relationship(back_populates="ciudadano")
    recordatorios: Mapped[list[Recordatorio]] = relationship(back_populates="ciudadano")

    def __repr__(self) -> str:
        return f"<Ciudadano id={self.id}>"
