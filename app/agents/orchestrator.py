"""Orquestador del agente: recibe un mensaje del ciudadano, corre el loop de function
calling de Gemini y devuelve la respuesta final de texto.

No contiene logica de negocio de dominio: cada capacidad concreta vive en una tool
independiente y testeable (app/agents/tools/). El orquestador solo sabe conversar con
el modelo y despachar llamadas a traves del tool_registry."""

from __future__ import annotations

import uuid
from typing import Any, cast

from google import genai
from google.genai import types

from app.agents.prompts import SYSTEM_PROMPT
from app.agents.tools import tool_registry
from app.agents.tools.validate_document import imagen_actual
from app.core.config import get_settings
from app.core.gemini_retry import generar_con_fallback, modelos_con_fallback
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_TOOL_ITERATIONS = 6


class TramiteOrchestrator:
    """Ejecuta el loop de agente (mensaje -> tool use -> respuesta) para una conversacion."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._modelos = modelos_con_fallback(settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL)
        self._max_tokens = settings.GEMINI_MAX_TOKENS

    async def responder(
        self,
        historial: list[dict[str, str]],
        mensaje_ciudadano: str,
        ciudadano_id: uuid.UUID,
        imagen: tuple[bytes, str] | None = None,
    ) -> str:
        """Procesa un turno de conversacion y devuelve el texto de respuesta del agente.

        `historial` son turnos previos como `{"role": "user"|"model", "content": str}`
        (Gemini usa "model" donde Anthropic/OpenAI usan "assistant"). `ciudadano_id` se
        inyecta como contexto interno (el modelo lo necesita para llamar
        iniciar_tramite, listar_tramites_ciudadano y programar_recordatorio — nunca
        podria adivinar un UUID por su cuenta). `imagen` (bytes, media_type) se deja
        disponible para la tool validar_documento durante este turno via contextvar
        (nunca se persiste), y ademas se le avisa al modelo por texto que llego una
        foto: sin ese aviso el modelo no tiene forma de saber que hay una imagen
        adjunta, ya que la tool es el unico canal por el que "ve" la foto."""
        token = imagen_actual.set(imagen) if imagen is not None else None
        try:
            contents: list[types.Content] = [
                types.Content(
                    role=turno["role"], parts=[types.Part.from_text(text=turno["content"])]
                )
                for turno in historial
            ]

            mensaje_para_modelo = mensaje_ciudadano
            if imagen is not None:
                nota = "[El ciudadano acaba de adjuntar una foto de un documento en este mensaje.]"
                mensaje_para_modelo = f"{mensaje_ciudadano}\n{nota}" if mensaje_ciudadano else nota

            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=mensaje_para_modelo)])
            )

            contexto_interno = (
                "\n\nContexto interno de esta conversacion (no se lo repitas al "
                'ciudadano de forma literal ni menciones que es un "contexto interno" '
                f"o un ID técnico; es solo para que uses las tools correctamente): "
                f"ciudadano_id={ciudadano_id}."
            )
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT + contexto_interno,
                tools=tool_registry.gemini_tools(),
                max_output_tokens=self._max_tokens,
            )

            for _ in range(_MAX_TOOL_ITERATIONS):
                response = await self._generate(contents, config)
                if not response.candidates:
                    return "No tengo una respuesta para eso en este momento."
                candidate = response.candidates[0]
                assert candidate.content is not None and candidate.content.parts is not None
                parts = candidate.content.parts
                function_calls = [part.function_call for part in parts if part.function_call]

                if not function_calls:
                    return _extraer_texto(parts)

                # Se reenvia el turno del modelo tal cual (incluye thought_signature) para
                # que Gemini mantenga continuidad de razonamiento entre llamadas a tools.
                contents.append(candidate.content)

                function_response_parts: list[types.Part] = []
                for call in function_calls:
                    nombre = call.name or ""
                    logger.info("agent_tool_call", tool_name=nombre)
                    resultado = await tool_registry.ejecutar(nombre, dict(call.args or {}))
                    function_response_parts.append(
                        types.Part.from_function_response(name=nombre, response=resultado)
                    )
                contents.append(types.Content(role="user", parts=function_response_parts))

            return (
                "Estoy teniendo dificultades para completar esta consulta. "
                "Por favor intenta reformularla o contacta a una oficina del GAMLP."
            )
        finally:
            if token is not None:
                imagen_actual.reset(token)

    async def _generate(
        self, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        # list[] es invariante para mypy: list[Content] no matchea estructuralmente
        # el ContentListUnion que pide generate_content aunque Content sea una de sus
        # alternativas. cast() es solo para mypy; en runtime no hace nada.
        contenido_para_generar = cast(types.ContentListUnion, contents)

        async def llamar(modelo: str) -> types.GenerateContentResponse:
            return await self._client.aio.models.generate_content(
                model=modelo, contents=contenido_para_generar, config=config
            )

        return await generar_con_fallback(self._modelos, llamar)


def _extraer_texto(parts: list[Any]) -> str:
    textos = [part.text for part in parts if getattr(part, "text", None)]
    return "\n".join(textos).strip() or "No tengo una respuesta para eso en este momento."
