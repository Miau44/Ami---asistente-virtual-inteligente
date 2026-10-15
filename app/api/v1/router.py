"""Router agregador de la version v1 de la API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import dashboard, documentos, health, normativa, recordatorios, tramites, webhooks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(webhooks.router)
api_router.include_router(tramites.router)
api_router.include_router(documentos.router)
api_router.include_router(normativa.router)
api_router.include_router(recordatorios.router)
api_router.include_router(dashboard.router)
