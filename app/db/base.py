"""Declarative base y punto unico de importacion de todos los modelos ORM,
requerido por Alembic para autogenerar migraciones."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM."""


class TimestampMixin:
    """Mixin que agrega created_at / updated_at consistentes en todas las tablas."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
