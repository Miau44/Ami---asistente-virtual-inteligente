"""POST /api/v1/webhooks/whatsapp - recibe mensajes entrantes de WhatsApp via Twilio.

Verifica X-Twilio-Signature ANTES de procesar cualquier payload (requisito de
seguridad no negociable). Sin firma valida, responde 401 y no toca la base de datos
ni invoca al agente.

Antes de invocar al orquestador (LLM), se revisa si el mensaje es un comando
deterministico (boton de "Borrar historial" / "Ver mis tramites" del menu de quick-reply,
o el texto equivalente escrito a mano) — esos casos no necesitan pasar por el modelo."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, Request

from app.agents.orchestrator import TramiteOrchestrator
from app.api.v1.deps import rate_limiter
from app.core.config import Settings, get_settings
from app.core.exceptions import InvalidWebhookSignatureError, MunicipalAPIUnavailableError
from app.core.logging import get_logger
from app.core.security import verify_twilio_signature
from app.db.models.conversacion import RolMensaje
from app.db.models.tramite import Tramite
from app.db.session import AsyncSessionLocal
from app.integrations.factory import get_esitram_client
from app.integrations.whatsapp_client import WhatsAppClient
from app.models.common import ApiModel
from app.services.conversacion_service import ConversacionService
from app.services.tramite_service import TramiteService

router = APIRouter(tags=["webhooks"])
logger = get_logger(__name__)

_COMANDO_BORRAR_HISTORIAL = {"borrar historial", "borrar mi historial"}
_COMANDO_VER_TRAMITES = {
    "ver mis tramites",
    "ver tramites",
    "ver historial de consultas",
    "ver historial",
}
_COMANDO_MENU = {"menu", "opciones", "ayuda"}

_ESTADO_EMOJI = {
    "iniciado": "🆕",
    "en_revision": "🔎",
    "observado": "⚠️",
    "aprobado": "✅",
    "rechazado": "❌",
    "vencido": "⏰",
}


class WebhookAck(ApiModel):
    recibido: bool


@router.post(
    "/webhooks/whatsapp",
    response_model=WebhookAck,
    summary="Webhook entrante de WhatsApp (Twilio)",
    dependencies=[Depends(rate_limiter(scope="webhook_whatsapp", limit_per_minute=60))],
)
async def whatsapp_webhook(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> WebhookAck:
    settings = get_settings()
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    if settings.TWILIO_WEBHOOK_VALIDATE:
        if not x_twilio_signature:
            raise InvalidWebhookSignatureError("Falta X-Twilio-Signature")
        url = str(request.url)
        verify_twilio_signature(settings.TWILIO_AUTH_TOKEN, url, params, x_twilio_signature)

    telefono = params.get("From", "")
    cuerpo = params.get("Body", "")
    num_media = int(params.get("NumMedia", "0") or "0")
    comando = cuerpo.strip().lower()

    imagen: tuple[bytes, str] | None = None
    if num_media > 0:
        media_url = params.get("MediaUrl0")
        media_type = params.get("MediaContentType0", "image/jpeg")
        if media_url:
            imagen = await _descargar_media(
                media_url, settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, media_type
            )

    async with AsyncSessionLocal() as session:
        conv_service = ConversacionService(session)
        ciudadano = await conv_service.obtener_o_crear_ciudadano(telefono)
        conversacion = await conv_service.obtener_conversacion_activa(ciudadano.id)
        es_conversacion_nueva = await _es_primer_turno(conv_service, conversacion.id)

        await conv_service.agregar_mensaje(conversacion.id, RolMensaje.CIUDADANO, cuerpo)

        if comando in _COMANDO_BORRAR_HISTORIAL:
            await conv_service.cerrar_conversacion(conversacion.id)
            respuesta = (
                "Listo, borre el historial de esta conversacion 🧹. Empecemos de nuevo: "
                "¿en que tramite te puedo ayudar hoy?"
            )
            await _enviar_respuesta(telefono, respuesta, settings, con_menu=True)
            logger.info(
                "whatsapp_webhook_procesado", num_media=num_media, comando="borrar_historial"
            )
            return WebhookAck(recibido=True)

        if comando in _COMANDO_VER_TRAMITES:
            tramite_service = TramiteService(session, get_esitram_client())
            tramites = await tramite_service.listar_por_ciudadano(ciudadano.id)
            respuesta = _formatear_tramites(tramites)
            await _enviar_respuesta(telefono, respuesta, settings, con_menu=True)
            logger.info("whatsapp_webhook_procesado", num_media=num_media, comando="ver_tramites")
            return WebhookAck(recibido=True)

        if comando in _COMANDO_MENU:
            await _enviar_respuesta(telefono, None, settings, con_menu=True)
            logger.info("whatsapp_webhook_procesado", num_media=num_media, comando="menu")
            return WebhookAck(recibido=True)

        historial_mensajes = await conv_service.historial(conversacion.id, limite=20)
        # Gemini usa los roles "user"/"model" (no "assistant" como Anthropic/OpenAI).
        historial_gemini: list[dict[str, str]] = [
            {
                "role": "user" if m.rol == RolMensaje.CIUDADANO else "model",
                "content": m.contenido,
            }
            for m in historial_mensajes[:-1]
        ]

        orchestrator = TramiteOrchestrator()
        respuesta = await orchestrator.responder(
            historial_gemini, cuerpo, ciudadano_id=ciudadano.id, imagen=imagen
        )

        await conv_service.agregar_mensaje(conversacion.id, RolMensaje.AGENTE, respuesta)

    # El mensaje del ciudadano y la respuesta del agente ya quedaron persistidos
    # arriba aunque el envio saliente falle: no queremos reprocesar todo el turno
    # (y potencialmente duplicar la respuesta) si Twilio reintenta este webhook
    # solo porque el envio de salida tuvo un problema transitorio. El menu solo se
    # reenvia en el primer turno de una conversacion (nueva o recien reiniciada),
    # para no repetirlo en cada mensaje.
    await _enviar_respuesta(telefono, respuesta, settings, con_menu=es_conversacion_nueva)

    logger.info("whatsapp_webhook_procesado", num_media=num_media)
    return WebhookAck(recibido=True)


async def _es_primer_turno(conv_service: ConversacionService, conversacion_id: uuid.UUID) -> bool:
    """True si esta conversacion (nueva o recien reiniciada con "borrar historial")
    todavia no tiene ningun mensaje — se usa para decidir si vale la pena reenviar el
    menu de botones sin repetirlo en cada turno."""
    historial = await conv_service.historial(conversacion_id, limite=1)
    return len(historial) == 0


async def _enviar_respuesta(
    telefono: str, texto: str | None, settings: Settings, *, con_menu: bool
) -> None:
    whatsapp = WhatsAppClient()
    try:
        if texto:
            await whatsapp.enviar_mensaje(telefono, texto)
        if con_menu and settings.TWILIO_MENU_CONTENT_SID:
            await whatsapp.enviar_menu(telefono, settings.TWILIO_MENU_CONTENT_SID)
    except MunicipalAPIUnavailableError:
        logger.warning("whatsapp_reply_send_failed")


def _formatear_tramites(tramites: list[Tramite]) -> str:
    if not tramites:
        return (
            "Todavia no tienes ningun tramite registrado con nosotros 📋. Cuentame en "
            "que te puedo ayudar y lo vemos juntos."
        )
    lineas = ["Estos son tus tramites registrados 📋:", ""]
    for tramite in tramites:
        emoji = _ESTADO_EMOJI.get(tramite.estado.value, "📄")
        codigo = tramite.codigo_externo or "sin codigo asignado todavia"
        tipo = tramite.tipo_tramite.replace("_", " ").title()
        estado = tramite.estado.value.replace("_", " ")
        lineas.append(f"{emoji} {tipo} — {codigo} — estado: {estado}")
    return "\n".join(lineas)


async def _descargar_media(
    media_url: str, account_sid: str, auth_token: str, media_type: str
) -> tuple[bytes, str] | None:
    """Descarga la imagen adjunta de Twilio en memoria (no se escribe a disco).

    Las URLs de media de Twilio responden con un 307 hacia la ubicacion real del
    archivo (a veces en otro host); httpx no sigue redirects por defecto, asi que sin
    follow_redirects=True la descarga siempre fallaba con "307 Temporary Redirect" —
    la foto nunca llegaba a validar_documento, sin importar que tan bien estuviera el
    resto del flujo."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(media_url, auth=(account_sid, auth_token))
            response.raise_for_status()
            return response.content, media_type
    except httpx.HTTPError as exc:
        logger.warning("whatsapp_media_download_failed", error_type=type(exc).__name__)
        return None
