"""Script de ingesta: toma texto/PDF de normativa oficial, lo divide en chunks,
genera embeddings y los guarda en ChromaDB. Tambien registra la fuente en Postgres
(tabla fuentes_normativa) para poder citarla en toda respuesta del agente.

Uso:
    python -m app.ingestion.ingest_normativa --archivo docs/normativa/ordenanza_123.pdf \
        --titulo "Ordenanza Municipal 123/2024" --numero-norma "OM 123/2024" \
        --fecha-vigencia 2024-01-15 --url https://lapaz.bo/normativa/123
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from app.core.logging import get_logger
from app.db.models.fuente_normativa import FuenteNormativa
from app.db.session import AsyncSessionLocal
from app.ingestion.chunking import dividir_en_chunks
from app.services.rag_service import RagService

logger = get_logger(__name__)


def _leer_texto(ruta: Path) -> str:
    if ruta.suffix.lower() == ".pdf":
        reader = PdfReader(str(ruta))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return ruta.read_text(encoding="utf-8")


async def ingest(
    archivo: Path,
    titulo: str,
    numero_norma: str | None,
    fecha_vigencia: date,
    url: str | None,
) -> None:
    texto = _leer_texto(archivo)
    chunks = dividir_en_chunks(texto)

    fuente_id = uuid.uuid4()
    rag_service = RagService()

    async with AsyncSessionLocal() as session:
        fuente = FuenteNormativa(
            id=fuente_id,
            titulo=titulo,
            numero_norma=numero_norma,
            fecha_vigencia=fecha_vigencia,
            url_fuente=url,
            chroma_collection=rag_service.collection_name,
        )
        session.add(fuente)
        await session.commit()

    rag_service.indexar_chunks(
        fuente_id=str(fuente_id),
        titulo=titulo,
        numero_norma=numero_norma,
        fecha_vigencia=fecha_vigencia.isoformat(),
        url_fuente=url,
        chunks=[c.texto for c in chunks],
    )

    logger.info("normativa_ingerida", fuente_id=str(fuente_id), total_chunks=len(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de normativa oficial al RAG")
    parser.add_argument("--archivo", required=True, type=Path)
    parser.add_argument("--titulo", required=True)
    parser.add_argument("--numero-norma", default=None)
    parser.add_argument("--fecha-vigencia", required=True, type=date.fromisoformat)
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    asyncio.run(ingest(args.archivo, args.titulo, args.numero_norma, args.fecha_vigencia, args.url))


if __name__ == "__main__":
    main()
