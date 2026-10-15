# Contrato de API - AMI Copiloto Backend

Base URL: `http://localhost:8000/api/v1` (local) — todos los paths abajo son
relativos a esa base.

Formato de error estandar en toda la API (cualquier codigo != 2xx):

```json
{ "error_code": "not_found", "message": "Tramite ... no encontrado" }
```

`error_code` posibles: `invalid_webhook_signature`, `invalid_credentials`,
`not_found`, `rate_limit_exceeded`, `municipal_api_unavailable`,
`document_validation_error`, `internal_error`. Errores de validacion de entrada
(Pydantic) devuelven `422` con el formato estandar de FastAPI (`detail: [...]`).

---

## Autenticacion (dashboard)

Todas las rutas bajo `/dashboard/*` excepto `/dashboard/auth/login` y
`/dashboard/auth/refresh` requieren header `Authorization: Bearer <access_token>`.

### POST /dashboard/auth/login

Request:
```json
{ "username": "admin", "password": "..." }
```

Response `200`:
```json
{ "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer" }
```

`access_token` expira en `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 15 min).
`401 invalid_credentials` si las credenciales son incorrectas.

### POST /dashboard/auth/refresh

Request:
```json
{ "refresh_token": "eyJ..." }
```

Response `200`: mismo shape que login (nuevo par access/refresh).

### GET /dashboard/resumen

Requiere Bearer token. Response `200`:
```json
{
  "total_ciudadanos": 42,
  "total_tramites": 57,
  "tramites_por_estado": { "iniciado": 10, "en_revision": 20, "aprobado": 27 },
  "documentos_validados_ultimos_7_dias": 15,
  "recordatorios_pendientes": 8
}
```

---

## Health

### GET /health

Sin autenticacion, sin rate limit. Response `200`:
```json
{ "status": "ok", "service": "ami-copiloto-backend" }
```

---

## Tramites

### GET /tramites/{tramite_id}

Response `200`:
```json
{
  "id": "uuid",
  "ciudadano_id": "uuid",
  "tipo_tramite": "licencia_funcionamiento",
  "sistema_origen": "esitram",
  "codigo_externo": "ESITRAM-MOCK-A1B2C3D4",
  "estado": "en_revision",
  "metadata_tramite": {},
  "created_at": "2026-07-20T10:00:00Z",
  "updated_at": "2026-07-20T10:00:00Z"
}
```
`estado` es uno de: `iniciado`, `en_revision`, `observado`, `aprobado`, `rechazado`,
`vencido`. `404 not_found` si no existe.

### GET /tramites?ciudadano_id={uuid}

Response `200`: array del mismo shape que arriba.

### GET /tramites?codigo_externo={string}

Busca por el codigo de seguimiento (el que conoce el ciudadano, ej.
`ESITRAM-MOCK-XXXX`), util para un funcionario que no tiene a mano el UUID interno.
Response `200`: array de 0 o 1 elemento, mismo shape que arriba (`[]` si no existe).

Debe indicarse `ciudadano_id` o `codigo_externo` (al menos uno); sin ninguno de los
dos, `422`.

### POST /tramites

Request:
```json
{
  "ciudadano_id": "uuid",
  "tipo_tramite": "licencia_funcionamiento",
  "sistema_origen": "esitram",
  "metadata_tramite": { "actividad_economica": "venta de electrodomesticos", "nombre_comercial": "ElectroHogar Sopocachi" }
}
```
Response `201`: mismo shape que GET. Internamente dispara `iniciar_tramite` en el
sistema municipal configurado (mock por defecto).

---

## Documentos

### POST /documentos/validar

`multipart/form-data`:
- `tramite_id` (string, uuid)
- `tipo_documento` (string, ej. `cedula_identidad`, `nit`, `plano`)
- `archivo` (file, imagen, max 8 MB)

Response `200`:
```json
{
  "tramite_id": "uuid",
  "tipo_documento": "cedula_identidad",
  "resultado": "aprobado",
  "observaciones": { "legible": true, "completo": true, "detalle": "..." }
}
```
`resultado` es uno de: `aprobado`, `observado`, `rechazado`. La imagen NUNCA se
persiste ni se devuelve; solo el resultado.

---

## Normativa (RAG)

### GET /normativa/buscar?consulta=...&top_k=5

Response `200` (encontrado):
```json
{
  "consulta": "requisitos licencia de funcionamiento",
  "encontrado": true,
  "fragmentos": [
    {
      "texto": "Se requiere licencia de funcionamiento vigente...",
      "similitud": 0.82,
      "fuente": {
        "titulo": "Ordenanza Municipal 123/2024",
        "numero_norma": "OM 123/2024",
        "fecha_vigencia": "2024-01-15",
        "url_fuente": "https://lapaz.bo/normativa/123"
      }
    }
  ]
}
```

Response `200` (sin resultados relevantes — el frontend debe mostrar esto como "sin
informacion oficial", no como error):
```json
{
  "consulta": "requisitos para viajar a la luna",
  "encontrado": false,
  "fragmentos": [],
  "mensaje": "No se encontro informacion oficial relevante para esta consulta."
}
```

---

## Recordatorios

### GET /recordatorios?ciudadano_id={uuid}

Response `200`:
```json
[
  {
    "id": "uuid",
    "ciudadano_id": "uuid",
    "tramite_id": "uuid",
    "mensaje": "Recuerda que tu licencia vence en 5 dias.",
    "fecha_programada": "2026-07-25T09:00:00Z",
    "estado": "pendiente"
  }
]
```
`estado`: `pendiente`, `enviado`, `cancelado`.

### POST /recordatorios

Requiere Bearer token de dashboard (uso administrativo).

Request:
```json
{
  "ciudadano_id": "uuid",
  "tramite_id": "uuid",
  "mensaje": "...",
  "fecha_programada": "2026-07-25T09:00:00Z"
}
```
Response `201`: mismo shape que GET. Idempotente: llamar dos veces con los mismos
`ciudadano_id` + `tramite_id` + `fecha_programada` devuelve el recordatorio ya
existente en vez de duplicarlo.

---

## Webhook de WhatsApp (uso interno de Twilio, no del frontend)

### POST /webhooks/whatsapp

`application/x-www-form-urlencoded`, formato estandar de Twilio
(`From`, `To`, `Body`, `NumMedia`, `MediaUrl0`, ...). Requiere header
`X-Twilio-Signature` valido o responde `401 invalid_webhook_signature` sin procesar
el payload. No relevante para el equipo de frontend salvo para entender el origen de
los datos que alimentan `/dashboard/resumen`.

---

## Rate limiting

Todos los endpoints publicos aplican rate limiting por IP (ventana fija de 60s). Al
excederlo: `429` con `error_code: rate_limit_exceeded`. Limites orientativos:
`/webhooks/whatsapp` 60/min, `/tramites` GET 30/min y POST 10/min,
`/documentos/validar` 20/min, `/normativa/buscar` 30/min.
