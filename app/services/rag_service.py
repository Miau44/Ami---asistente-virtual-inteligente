"""Servicio RAG: indexa y busca normativa oficial en ChromaDB.

Regla no-negociable: si no hay fragmentos por encima de RAG_SIMILARITY_THRESHOLD, el
servicio devuelve encontrado=False y NINGUN fragmento. Esto es lo que le permite al
agente responder "no tengo informacion oficial sobre esto" en vez de inventar (ver
app/agents/prompts.py y tests/unit/test_rag_anti_hallucination.py).

No importa nada de FastAPI: es logica de negocio pura, testeable de forma aislada.
"""

from __future__ import annotations

import uuid
from typing import Any

import chromadb

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RagService:
    """Encapsula el acceso a ChromaDB para busqueda semantica de normativa."""

    def __init__(self) -> None:
        settings = get_settings()
        self._threshold = settings.RAG_SIMILARITY_THRESHOLD
        self._top_k_default = settings.RAG_TOP_K
        self.collection_name = settings.CHROMA_COLLECTION_NORMATIVA
        self._client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        # Se fija explicitamente el espacio de distancia a coseno: Chroma usa "l2"
        # (distancia euclidiana) por defecto, que no es directamente convertible a la
        # similitud [0,1] que espera RAG_SIMILARITY_THRESHOLD. Solo aplica al crear la
        # coleccion por primera vez; una coleccion ya creada con otro espacio no se
        # puede migrar in-place (hay que recrearla).
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )

    def indexar_chunks(
        self,
        fuente_id: str,
        titulo: str,
        numero_norma: str | None,
        fecha_vigencia: str,
        url_fuente: str | None,
        chunks: list[str],
    ) -> None:
        """Agrega los chunks de un documento normativo a la coleccion vectorial."""
        if not chunks:
            return

        ids = [f"{fuente_id}-{i}" for i in range(len(chunks))]
        metadatas: list[dict[str, Any]] = [
            {
                "fuente_id": fuente_id,
                "titulo": titulo,
                "numero_norma": numero_norma or "",
                "fecha_vigencia": fecha_vigencia,
                "url_fuente": url_fuente or "",
            }
            for _ in chunks
        ]
        self._collection.add(ids=ids, documents=chunks, metadatas=metadatas)  # type: ignore[arg-type]

    def buscar(self, consulta: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Busca fragmentos relevantes. Solo devuelve resultados con similitud >= umbral.

        ChromaDB devuelve distancia (menor = mas similar); se convierte a similitud
        coseno aproximada como (1 - distancia) para comparar contra el umbral configurado.
        """
        k = top_k or self._top_k_default
        resultados = self._collection.query(query_texts=[consulta], n_results=k)

        documentos = (resultados.get("documents") or [[]])[0]
        metadatas = (resultados.get("metadatas") or [[]])[0]
        distancias = (resultados.get("distances") or [[]])[0]

        fragmentos: list[dict[str, Any]] = []
        for doc, meta, dist in zip(documentos, metadatas, distancias, strict=False):
            similitud = max(0.0, 1.0 - dist)
            if similitud < self._threshold:
                continue
            fragmentos.append({"texto": doc, "similitud": similitud, "metadata": meta})

        logger.info(
            "rag_busqueda",
            total_candidatos=len(documentos),
            total_relevantes=len(fragmentos),
            umbral=self._threshold,
        )
        return fragmentos


def nuevo_id_fuente() -> str:
    return str(uuid.uuid4())
