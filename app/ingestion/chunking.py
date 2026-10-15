"""Utilidades de chunking de texto normativo para ingestion al vector store.

Estrategia simple por parrafos con solapamiento, suficiente para reglamentos y
ordenanzas municipales (documentos estructurados en articulos/incisos cortos).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    texto: str
    indice: int


def dividir_en_chunks(
    texto: str, max_caracteres: int = 800, solapamiento: int = 100
) -> list[Chunk]:
    """Divide un texto largo en fragmentos de tamano acotado, con solapamiento para
    no cortar contexto relevante entre chunks consecutivos."""
    if max_caracteres <= solapamiento:
        raise ValueError("max_caracteres debe ser mayor que solapamiento")

    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    buffer = ""
    indice = 0

    for parrafo in parrafos:
        candidato = f"{buffer}\n\n{parrafo}".strip() if buffer else parrafo
        if len(candidato) <= max_caracteres:
            buffer = candidato
            continue

        if buffer:
            chunks.append(Chunk(texto=buffer, indice=indice))
            indice += 1
            cola = buffer[-solapamiento:] if len(buffer) > solapamiento else buffer
            buffer = f"{cola}\n\n{parrafo}".strip()
        else:
            # Un solo parrafo mas largo que max_caracteres: se corta a la fuerza.
            for inicio in range(0, len(parrafo), max_caracteres - solapamiento):
                trozo = parrafo[inicio : inicio + max_caracteres]
                chunks.append(Chunk(texto=trozo, indice=indice))
                indice += 1
            buffer = ""

    if buffer:
        chunks.append(Chunk(texto=buffer, indice=indice))

    return chunks
