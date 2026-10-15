"""Logica de negocio para validacion de documentos por vision.

La imagen se recibe como bytes en memoria, se envia al modelo multimodal y se
descarta inmediatamente despues de obtener el resultado: nunca se escribe a disco
ni se indexa en el vector store (ver docs/decisiones-tecnicas.md)."""

from __future__ import annotations

import json
import uuid
from typing import Any, cast

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.exceptions import DocumentValidationError
from app.core.gemini_retry import generar_con_fallback, modelos_con_fallback
from app.core.logging import get_logger
from app.db.models.documento_validado import DocumentoValidado, ResultadoValidacion
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)

_PROMPT_VALIDACION = """Eres un asistente que valida fotos de documentos oficiales bolivianos \
para tramites municipales del GAMLP. Analiza la imagen adjunta de un documento de tipo \
"{tipo_documento}" y determina si es apta para presentar en el tramite.

Criterios: "aprobado" si el documento es legible, completo y corresponde al tipo esperado. \
"observado" si hay problemas menores (foto borrosa, corte de bordes) que probablemente \
requieran repetir la foto. "rechazado" si el documento no corresponde al tipo esperado o \
esta vencido/ilegible.

Ademas, si el tipo de documento tiene un nombre de persona y un numero identificador \
visibles (ej. cedula_identidad, nit), extrae el nombre completo y el numero tal como \
aparecen escritos en la foto — esto permite confirmarle al ciudadano que se leyo \
correctamente antes de dar el documento por valido. Si el tipo de documento no tiene \
esos campos (ej. croquis_ubicacion, plano) o no se alcanzan a leer con confianza, deja \
nombre_completo y numero_documento como cadena vacia en vez de adivinar."""

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "resultado": {
            "type": "STRING",
            "enum": [r.value for r in ResultadoValidacion],
        },
        "observaciones": {
            "type": "OBJECT",
            "properties": {
                "legible": {"type": "BOOLEAN"},
                "completo": {"type": "BOOLEAN"},
                "detalle": {"type": "STRING", "description": "Explicacion breve, 1-2 oraciones."},
                "nombre_completo": {
                    "type": "STRING",
                    "description": (
                        "Nombre completo tal como aparece en el documento. Cadena vacia "
                        "si el tipo de documento no tiene nombre o no se lee con confianza."
                    ),
                },
                "numero_documento": {
                    "type": "STRING",
                    "description": (
                        "Numero de CI/NIT/identificador principal tal como aparece en el "
                        "documento. Cadena vacia si no aplica o no se lee con confianza."
                    ),
                },
            },
            "required": [
                "legible",
                "completo",
                "detalle",
                "nombre_completo",
                "numero_documento",
            ],
        },
    },
    "required": ["resultado", "observaciones"],
}


class DocumentoService:
    """Valida documentos via el modelo multimodal de Gemini, sin persistir la imagen."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._modelos = modelos_con_fallback(
            settings.GEMINI_VISION_MODEL, settings.GEMINI_VISION_FALLBACK_MODEL
        )

    async def validar(
        self,
        tramite_id: uuid.UUID,
        tipo_documento: str,
        imagen_bytes: bytes,
        media_type: str,
    ) -> DocumentoValidado:
        resultado_dict = await self._analizar_con_vision(tipo_documento, imagen_bytes, media_type)
        # imagen_bytes queda fuera de alcance aqui; no se guarda en ninguna variable persistente.

        documento = DocumentoValidado(
            tramite_id=tramite_id,
            tipo_documento=tipo_documento,
            resultado=ResultadoValidacion(resultado_dict["resultado"]),
            observaciones=resultado_dict["observaciones"],
        )
        async with AsyncSessionLocal() as session:
            session.add(documento)
            await session.commit()
            await session.refresh(documento)
        return documento

    async def _analizar_con_vision(
        self, tipo_documento: str, imagen_bytes: bytes, media_type: str
    ) -> dict[str, Any]:
        try:
            response = await self._generate(tipo_documento, imagen_bytes, media_type)
            data: dict[str, Any] = json.loads(response.text or "{}")
            return data
        except (
            Exception
        ) as exc:  # noqa: BLE001 - cualquier fallo de vision se traduce a error de dominio
            # Loggear el tipo/causa real ANTES de convertirlo en el mensaje generico
            # de dominio: sin esto, un 400/429/timeout de la API se ve identico a un
            # rechazo real por mala calidad de foto tanto en logs como para el
            # ciudadano, hasta que alguien lo reproduce a mano (ver ADR-013).
            logger.warning(
                "document_vision_analysis_failed",
                tipo_documento=tipo_documento,
                error_type=type(exc).__name__,
            )
            raise DocumentValidationError(
                "No se pudo analizar el documento. Intenta con otra foto mas clara."
            ) from exc

    async def _generate(
        self, tipo_documento: str, imagen_bytes: bytes, media_type: str
    ) -> types.GenerateContentResponse:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=imagen_bytes, mime_type=media_type),
                    types.Part.from_text(
                        text=_PROMPT_VALIDACION.format(tipo_documento=tipo_documento)
                    ),
                ],
            )
        ]
        # list[] es invariante para mypy: list[Content] no matchea estructuralmente
        # el ContentListUnion que pide generate_content aunque Content sea una de sus
        # alternativas. cast() es solo para mypy; en runtime no hace nada.
        contenido_para_generar = cast(types.ContentListUnion, contents)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            max_output_tokens=800,
            # Los modelos "-latest" de Gemini razonan por defecto ("thinking") y esos
            # tokens de pensamiento se descuentan de max_output_tokens — con thinking
            # sin acotar, este schema (objeto anidado con 5 campos) agotaba el
            # presupuesto antes de emitir el JSON final y devolvia texto truncado /
            # vacio (finish_reason=MAX_TOKENS, ver ADR-009). Pero thinking_budget=0
            # (desactivarlo del todo) SOLO funciona en "gemini-flash-lite-latest": en
            # "gemini-flash-latest" (el modelo completo, usado primero para vision
            # por mejor OCR, ver ADR-013) budget=0 devuelve
            # 400 INVALID_ARGUMENT — ese 400, atrapado por el except generico de
            # _analizar_con_vision, se le mostraba al ciudadano como "no se pudo
            # analizar el documento", indistinguible de un rechazo real por mala
            # calidad de foto. Un presupuesto chico pero no-cero (128) funciona en
            # ambos modelos. Verificado en vivo contra la API real.
            thinking_config=types.ThinkingConfig(thinking_budget=128),
        )

        async def llamar(modelo: str) -> types.GenerateContentResponse:
            return await self._client.aio.models.generate_content(
                model=modelo, contents=contenido_para_generar, config=config
            )

        return await generar_con_fallback(self._modelos, llamar)
