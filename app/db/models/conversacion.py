"""Modelos ORM: conversaciones y mensajes."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.ciudadano import Ciudadano


class RolMensaje(enum.StrEnum):
    CIUDADANO = "ciudadano"
    AGENTE = "agente"
    SISTEMA = "sistema"


class Conversacion(TimestampMixin, Base):
    """Hilo de conversacion de WhatsApp con un ciudadano."""

    __tablename__ = "conversaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ciudadano_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ciudadanos.id", ondelete="CASCADE"), nullable=False
    )
    activa: Mapped[bool] = mapped_column(default=True, nullable=False)

    ciudadano: Mapped[Ciudadano] = relationship(back_populates="conversaciones")
    mensajes: Mapped[list[Mensaje]] = relationship(
        back_populates="conversacion", order_by="Mensaje.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversacion id={self.id}>"


class Mensaje(TimestampMixin, Base):
    """Un mensaje individual dentro de una conversacion."""

    __tablename__ = "mensajes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversaciones.id", ondelete="CASCADE"), nullable=False
    )
    rol: Mapped[RolMensaje] = mapped_column(
        Enum(
            RolMensaje,
            name="rol_mensaje",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    conversacion: Mapped[Conversacion] = relationship(back_populates="mensajes")

    def __repr__(self) -> str:
        return f"<Mensaje id={self.id} rol={self.rol}>"
