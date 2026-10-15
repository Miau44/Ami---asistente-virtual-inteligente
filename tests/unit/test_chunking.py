"""Tests unitarios de la utilidad de chunking usada en ingestion de normativa."""

from __future__ import annotations

from app.ingestion.chunking import dividir_en_chunks


def test_dividir_en_chunks_texto_corto_produce_un_solo_chunk() -> None:
    texto = "Articulo 1. Este es un texto normativo breve de una sola seccion."
    chunks = dividir_en_chunks(texto, max_caracteres=800, solapamiento=100)

    assert len(chunks) == 1
    assert chunks[0].texto == texto


def test_dividir_en_chunks_respeta_tamano_maximo() -> None:
    parrafo = "Palabra " * 300  # texto largo forzado a dividirse
    chunks = dividir_en_chunks(parrafo, max_caracteres=200, solapamiento=40)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.texto) <= 200
