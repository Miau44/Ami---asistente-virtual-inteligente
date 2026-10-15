"""Modelo ORM: fuentes_normativa.

Metadata relacional de cada documento normativo ingerido al RAG. El contenido y los
embeddings viven en ChromaDB; aqui se guarda la fuente y fecha de vigencia para poder
citarlas en toda respuesta del agente (requisito de no-alucinacion)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FuenteNormativa(TimestampMixin, Base):
    """Documento normativo oficial (ordenanza, reglamento, etc.) ingerido al RAG."""

    __tablename__ = "fuentes_normativa"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    numero_norma: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fecha_vigencia: Mapped[date] = mapped_column(Date, nullable=False)
    url_fuente: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chroma_collection: Mapped[str] = mapped_column(String(120), nullable=False)

    def __repr__(self) -> str:
        return f"<FuenteNormativa id={self.id} titulo={self.titulo!r}>"
