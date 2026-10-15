"""Registro de tools del agente.

Cada tool se registra a si misma via @tool_registry.register al ser importada. El
orquestador no conoce las tools individualmente: itera el registro. Agregar una tool
nueva (nuevo tramite, nueva integracion) no requiere tocar orchestrator.py.
"""

from __future__ import annotations

# Importar cada modulo de tool para que se auto-registre en tool_registry.
from app.agents.tools import (  # noqa: E402,F401
    check_procedure_status,
    list_citizen_procedures,
    schedule_reminder,
    search_internet,
    search_regulations,
    start_procedure,
    validate_document,
)
from app.agents.tools.registry import ToolRegistry, tool_registry

__all__ = ["ToolRegistry", "tool_registry"]
