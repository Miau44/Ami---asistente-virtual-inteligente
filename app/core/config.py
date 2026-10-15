"""Configuracion central de la aplicacion, leida desde variables de entorno."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion tipada de la aplicacion. Ver .env.example para el listado completo."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App general ---
    APP_ENV: Literal["local", "staging", "production"] = "local"
    APP_DEBUG: bool = True
    APP_NAME: str = "ami-copiloto-backend"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = "change-me"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    # --- Base de datos ---
    DATABASE_URL: str = "postgresql+asyncpg://ami:ami@localhost:5432/ami_copiloto"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://ami:ami@localhost:5432/ami_copiloto"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- ChromaDB / RAG ---
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NORMATIVA: str = "normativa_municipal"
    # Calibrado empiricamente contra el modelo de embeddings por defecto de ChromaDB
    # (all-MiniLM-L6-v2, similitud coseno): consultas irrelevantes midieron ~0.20-0.38
    # de similitud contra el corpus de demo, consultas relevantes ~0.50-0.54. 0.45 separa
    # ambos grupos con margen. Ver docs/decisiones-tecnicas.md ADR-006.
    RAG_SIMILARITY_THRESHOLD: float = 0.45
    RAG_TOP_K: int = 5

    # --- Gemini (Google GenAI) ---
    # "gemini-flash-lite-latest" tiene su propio cupo gratuito, separado del de
    # "gemini-flash-latest" (que se agoto en horas durante el desarrollo: el
    # nivel gratuito de "-latest" resolvia a "gemini-3.5-flash" con limite de
    # solo 20 requests/dia). Los IDs de modelo fijos (ej. "gemini-2.0-flash")
    # tampoco tienen cupo gratuito para esta key. Ver docs/decisiones-tecnicas.md
    # ADR-009 y ADR-010 antes de cambiar este default.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-lite-latest"
    # Si GEMINI_MODEL agota su cupo diario (429), se reintenta automaticamente con
    # este alias antes de fallar la conversacion. Ver app/core/gemini_retry.py.
    GEMINI_FALLBACK_MODEL: str = "gemini-flash-latest"
    GEMINI_MAX_TOKENS: int = 1024

    # DocumentoService (validacion de fotos) usa un par de modelos separado del chat:
    # "-lite" prioriza velocidad/costo, que sirve para conversar, pero tiene peor OCR
    # en documentos densos (ej. certificados de NIT con texto chico, tablas, QR) que
    # "gemini-flash-latest" (modelo completo). Se prueba el completo primero aqui y
    # se cae al lite solo si se agota su cupo — al reves que en el chat. Ver ADR-013.
    GEMINI_VISION_MODEL: str = "gemini-flash-latest"
    GEMINI_VISION_FALLBACK_MODEL: str = "gemini-flash-lite-latest"

    # --- Tavily (busqueda web real, complementa el RAG de normativa) ---
    # Vacio = la tool buscar_en_internet responde "no configurada" en vez de fallar.
    TAVILY_API_KEY: str = ""
    TAVILY_MAX_RESULTS: int = 4

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Twilio ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+10000000000"
    TWILIO_WEBHOOK_VALIDATE: bool = True
    # ContentSid del Content Template de quick-reply creado por
    # scripts/setup_whatsapp_menu.py. Vacio = no se manda menu de botones.
    TWILIO_MENU_CONTENT_SID: str = ""

    # --- Rate limiting ---
    RATE_LIMIT_MESSAGES_PER_MINUTE: int = 10
    RATE_LIMIT_DOCUMENTS_PER_HOUR: int = 20

    # --- Integraciones municipales ---
    ESITRAM_MODE: Literal["mock", "real"] = "mock"
    ESITRAM_API_URL: str = ""
    ESITRAM_API_KEY: str = ""
    ESITRAM_TIMEOUT_SECONDS: int = 8

    IGOB_MODE: Literal["mock", "real"] = "mock"
    IGOB_API_URL: str = ""
    IGOB_API_KEY: str = ""
    IGOB_TIMEOUT_SECONDS: int = 8

    GESTION_DOCUMENTAL_MODE: Literal["mock", "real"] = "mock"
    GESTION_DOCUMENTAL_API_URL: str = ""
    GESTION_DOCUMENTAL_API_KEY: str = ""

    # --- Proactividad ---
    PROACTIVE_ENGINE_INTERVAL_MINUTES: int = 30
    PROACTIVE_ENGINE_ENABLED: bool = True

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de Settings (singleton por proceso)."""
    return Settings()
