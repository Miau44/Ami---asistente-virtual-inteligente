"""Tool registry: mapea nombre de tool -> definicion (schema + handler async).

Usar un registro en vez de un if/elif gigante en el orquestador permite que el
numero de tools crezca (nuevos tipos de tramite, nuevas integraciones) sin
reescribir el loop del agente."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from google.genai import types

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _a_schema_gemini(json_schema: dict[str, Any]) -> dict[str, Any]:
    """Convierte un JSON Schema (tipos en minuscula: "object", "string", ...) al formato
    que espera `FunctionDeclaration.parameters` de Gemini (tipos en mayuscula: "OBJECT",
    "STRING", ...). Nuestros input_schema ya son JSON Schema valido; Gemini exige el
    mismo shape pero con los valores de "type" en mayuscula."""
    resultado: dict[str, Any] = dict(json_schema)
    if "type" in resultado and isinstance(resultado["type"], str):
        resultado["type"] = resultado["type"].upper()
    if "properties" in resultado:
        resultado["properties"] = {
            key: _a_schema_gemini(value) for key, value in resultado["properties"].items()
        }
    if "items" in resultado and isinstance(resultado["items"], dict):
        resultado["items"] = _a_schema_gemini(resultado["items"])
    return resultado


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    """Registro central de tools disponibles para el agente orquestador."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(handler: ToolHandler) -> ToolHandler:
            self._tools[name] = ToolDefinition(
                name=name, description=description, input_schema=input_schema, handler=handler
            )
            return handler

        return decorator

    def gemini_tools(self) -> list[types.Tool]:
        """Formato esperado por `GenerateContentConfig.tools` del SDK de Gemini."""
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=_a_schema_gemini(t.input_schema),
            )
            for t in self._tools.values()
        ]
        return [types.Tool(function_declarations=declarations)]

    async def ejecutar(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"error": f"Tool desconocida: {name}"}
        return await self._tools[name].handler(tool_input)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


tool_registry = ToolRegistry()
