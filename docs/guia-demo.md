# Guia de demo / MVP

Esta guia describe como levantar AMI Copiloto de punta a punta para una demo
convincente **sin** depender de credenciales reales de e-SITRAM/iGOB (que llegaran
mas adelante) ni, si se quiere, de un numero de WhatsApp real de Twilio.

Este flujo completo (build, migraciones, seed, ingesta de normativa, busqueda RAG,
creacion de tramite, dashboard) se corrio y verifico de punta a punta contra **Docker
dentro de WSL Ubuntu**, que es el setup recomendado en Windows — corre todos los
comandos de esta guia desde una terminal de WSL (`wsl` en cmd/PowerShell, o la app de
tu distro), no desde PowerShell/cmd directamente, aunque el proyecto viva en una
carpeta de Windows (`/mnt/c/...` o `/mnt/e/...`).

## 1. Que es indispensable y que es opcional

| Componente | Estado para la demo | Que hacer |
|---|---|---|
| `GEMINI_API_KEY` | **Indispensable** | No hay modo mock para el LLM/vision: sin esta key el agente no responde ni valida documentos. Conseguir una key gratis en https://aistudio.google.com/apikey (solo necesitas una cuenta de Google, sin tarjeta). Dejar `GEMINI_MODEL=gemini-flash-latest` (el default) — los IDs de modelo fijos como `gemini-2.0-flash` pueden reportar cuota gratuita 0 para keys nuevas, ver ADR-009 en `decisiones-tecnicas.md` |
| Embeddings del RAG | **No requiere ninguna key** | ChromaDB descarga y corre localmente su propio modelo (`all-MiniLM-L6-v2`, ONNX, ~80 MB) la primera vez que se indexa o busca. Esa descarga tarda 15-30s la primera vez; corridas posteriores son instantaneas |
| `ESITRAM_MODE` / `IGOB_MODE` | Ya en `mock` por defecto | No requiere accion. Los mocks generan codigos de tramite y estados deterministicos (`app/integrations/esitram_mock.py`, `igob_mock.py`) |
| Docker Desktop con integracion WSL (o Docker Engine nativo en la distro) | **Indispensable** para el flujo con un solo comando | Levanta Postgres, Redis, ChromaDB, la API y el worker. Verificado con `docker compose` v5 corriendo dentro de WSL Ubuntu |
| `TWILIO_*` | **Opcional para la demo** | Si no tienes un sandbox de WhatsApp de Twilio a mano, se puede demostrar todo el flujo pegandole directo a la API REST (seccion 4) sin pasar por WhatsApp. Si quieres el flujo real por WhatsApp, usa el sandbox gratuito de Twilio (`https://www.twilio.com/docs/whatsapp/sandbox`) y pon `TWILIO_WEBHOOK_VALIDATE=false` solo en ese entorno de pruebas si necesitas simular peticiones sin firma valida |
| `JWT_SECRET_KEY`, `APP_SECRET_KEY` | Indispensable (cualquier valor) | Genera algo random, ej. `openssl rand -hex 32`. El usuario admin del dashboard usa `APP_SECRET_KEY` como contrasena (ver ADR-007 en `decisiones-tecnicas.md`) |

## 2. Levantar el stack

```bash
cp .env.example .env
# Edita .env y completa como minimo:
#   GEMINI_API_KEY=...
#   APP_SECRET_KEY=<valor random>
#   JWT_SECRET_KEY=<valor random>
# Deja ESITRAM_MODE=mock e IGOB_MODE=mock (default) para la demo.

./scripts/demo_reset.sh
```

`demo_reset.sh` hace, en orden: baja contenedores previos, reconstruye imagenes,
levanta Postgres/Redis/ChromaDB, aplica las migraciones de Alembic, siembra datos
ficticios (`scripts/seed_data.py`) e **ingesta un documento de normativa de
ejemplo al RAG** (`docs/normativa/ejemplo_licencia_funcionamiento.txt`) para que
`buscar_normativa` tenga contexto real que citar desde el primer momento. Al
terminar, la API queda arriba en `http://localhost:8000/api/v1/health`.

El escenario sembrado es **Daniela Choque**, quien quiere abrir "ElectroHogar
Sopocachi" (venta de electrodomesticos en la zona de Sopocachi) y ya tiene un
tramite de licencia de funcionamiento en revision. A diferencia de versiones
anteriores de este script, los IDs son **fijos** (no aleatorios) para que se
puedan usar directamente en una demo sin consultar psql:

| Entidad | ID fijo |
|---|---|
| `ciudadano_id` (Daniela Choque) | `00000000-0000-0000-0000-000000000001` |
| `tramite_id` (licencia de funcionamiento, `en_revision`) | `00000000-0000-0000-0000-000000000002` |
| `recordatorio_id` | `00000000-0000-0000-0000-000000000004` |

El flujo completo de esta demo, mostrado paso a paso desde el dashboard
(`ami-copiloto-dashboard`), esta documentado en
`ami-copiloto-dashboard/docs/demo-sopocachi.md`.

Documentacion interactiva de la API: `http://localhost:8000/docs`.

## 3. Verificar que todo esta arriba

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","service":"ami-copiloto-backend"}
```

## 4. Flujo demostrativo sin WhatsApp (recomendado si no hay sandbox de Twilio a mano)

El webhook de WhatsApp exige firma valida de Twilio por seguridad (ver ADR y
`app/core/security.py`), asi que para una demo rapida sin Twilio configurado, el
camino mas simple es mostrar cada capacidad directamente contra la API REST — el
orquestador y las tools son los mismos que usaria el flujo de WhatsApp, solo cambia
el canal de entrada.

**a) Busqueda de normativa (RAG, con fuente citada):**
```bash
curl "http://localhost:8000/api/v1/normativa/buscar?consulta=requisitos+licencia+de+funcionamiento"
```
Devuelve el fragmento ingestado en el paso 2, con `fuente.titulo` y
`fuente.fecha_vigencia` — asi se demuestra la regla de "nunca inventar" (compara
con una consulta fuera de tema, ver seccion 5).

**b) Iniciar un tramite (contra e-SITRAM en modo mock):**
```bash
curl -X POST http://localhost:8000/api/v1/tramites \
  -H "Content-Type: application/json" \
  -d '{"ciudadano_id":"00000000-0000-0000-0000-000000000001","tipo_tramite":"licencia_funcionamiento","sistema_origen":"esitram","metadata_tramite":{"actividad_economica":"venta de electrodomesticos","nombre_comercial":"ElectroHogar Sopocachi"}}'
```
El `ciudadano_id` de arriba es el de Daniela Choque, sembrado por
`scripts/seed_data.py` (ver tabla de IDs fijos mas arriba). Tambien se puede
confirmar conectandose a Postgres
(`docker compose exec postgres psql -U ami -d ami_copiloto -c "select id, telefono_whatsapp from ciudadanos;"`).

**c) Validar un documento por foto (vision):**
```bash
curl -X POST http://localhost:8000/api/v1/documentos/validar \
  -F "tramite_id=<uuid-del-tramite>" \
  -F "tipo_documento=cedula_identidad" \
  -F "archivo=@/ruta/a/una/foto.jpg"
```
Muestra el resultado (`aprobado`/`observado`/`rechazado`) sin persistir la imagen
(ver ADR-002).

**d) Dashboard administrativo (resumen agregado):**
```bash
curl -X POST http://localhost:8000/api/v1/dashboard/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<valor de APP_SECRET_KEY>"}'
# copiar el access_token de la respuesta
curl http://localhost:8000/api/v1/dashboard/resumen \
  -H "Authorization: Bearer <access_token>"
```

## 5. Demostrar el comportamiento anti-alucinacion

```bash
curl "http://localhost:8000/api/v1/normativa/buscar?consulta=requisitos+para+viajar+a+la+luna"
```
Debe devolver `"encontrado": false` y `fragmentos: []` — es el mismo contrato que
verifica `tests/unit/test_rag_anti_hallucination.py`. Es el punto mas fuerte de la
demo para explicar por que el agente no inventa requisitos.

## 6. Flujo completo por WhatsApp (si hay sandbox de Twilio disponible)

1. Configura un sandbox en https://www.twilio.com/docs/whatsapp/sandbox y copia
   `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_NUMBER` a `.env`.
2. Expone `http://localhost:8000` a internet (ej. `ngrok http 8000`) y configura esa
   URL + `/api/v1/webhooks/whatsapp` como webhook entrante en la consola de Twilio.
3. Escribe al numero del sandbox desde tu WhatsApp. El mensaje llega firmado por
   Twilio, se verifica la firma (`app/core/security.py::verify_twilio_signature`) y
   el orquestador responde usando las mismas tools que en el flujo REST.

## 7. Ingestar normativa real del GAMLP (para ir mas alla del ejemplo de demo)

El indice publico https://lapaz.bo/tramites-y-servicios-gamlp/ confirma las
categorias de tramite reales (licencia de funcionamiento, catastro, RUAT, patentes,
permisos, etc.) pero es un indice de navegacion, no el texto legal en si — no
expone directamente PDFs de ordenanzas por tramite. Para reemplazar el contenido de
ejemplo por normativa oficial:

1. Navega desde esa pagina hasta el tramite especifico que quieras cubrir y ubica el
   enlace a "Normativa" o al reglamento/ordenanza aplicable (usualmente un PDF).
2. Descarga ese PDF localmente.
3. Ingierelo con el numero de norma y fecha de vigencia reales que indique el
   documento:
   ```bash
   docker compose run --rm api python -m app.ingestion.ingest_normativa \
     --archivo /ruta/al/pdf/descargado.pdf \
     --titulo "Titulo exacto de la norma" \
     --numero-norma "OM XXX/AAAA" \
     --fecha-vigencia AAAA-MM-DD \
     --url https://lapaz.bo/... (URL de la fuente)
   ```
4. Repite por cada tramite que quieras que el agente pueda responder con fuente
   verificable. Mientras no se ingeste una norma, `buscar_normativa` seguira
   devolviendo `encontrado: false` para ese tema — es el comportamiento esperado, no
   un bug (ver seccion 5).

**Importante:** no se debe alimentar al RAG con texto redactado por el LLM o
parafraseado sin verificar contra la fuente oficial; eso reintroduciria el riesgo de
alucinacion que el ADR-006 busca evitar. Solo texto extraido literalmente de un PDF
o pagina oficial del GAMLP.

## 8. Conectar e-SITRAM / iGOB reales cuando esten disponibles

Sin tocar codigo de negocio: en `.env`, cambiar `ESITRAM_MODE=real` (o `IGOB_MODE=real`)
y completar `ESITRAM_API_URL` / `ESITRAM_API_KEY` (o los equivalentes de iGOB). Ver
`app/integrations/factory.py` y ADR-001 en `docs/decisiones-tecnicas.md`.

## 9. Problemas frecuentes (encontrados corriendo el stack real)

**`port is already allocated` al levantar Postgres.** Algun otro proyecto o un
Postgres nativo ya esta usando el puerto 5432 del host (comun si trabajas con varios
proyectos Docker a la vez). Por eso `docker-compose.yml` mapea Postgres al **5433** del
host por defecto (`docker compose exec postgres psql -U ami -d ami_copiloto` sigue
funcionando igual, ya que corre dentro del contenedor y no depende del puerto host). Si
igual choca, revisa `docker ps -a` para ver que otro contenedor esta usando el puerto y
cambia el mapeo en `docker-compose.yml`.

**Cambie una variable en `.env` pero no se aplica.** `docker compose restart <servicio>`
reinicia el proceso **con las variables de entorno que ya tenia el contenedor al
crearse** — no relee `.env`. Despues de editar `.env`, usa:
```bash
docker compose up -d --force-recreate api
```
(o `worker`, segun corresponda) para que el contenedor se recree con los valores
nuevos. `docker compose down && docker compose up -d` tambien funciona, pero
`--force-recreate api` es mas rapido si Postgres/Redis/Chroma ya estan arriba.

**La primera busqueda o ingesta de normativa tarda ~15-30 segundos.** Es la descarga
del modelo de embeddings (`all-MiniLM-L6-v2`, ~80 MB) que ChromaDB hace en el momento,
no un cuelgue. Con `docker compose run --rm api ...` (usado por `demo_reset.sh` y en
la seccion 7) esa descarga se repite cada vez porque el contenedor `run` es efimero; si
vas a ingestar varios documentos de normativa en una sesion de trabajo, es mas rapido
entrar a un shell del contenedor (`docker compose exec api sh`) y correr varias
ingestas ahi dentro, en vez de un `docker compose run` por documento.

**Al construir la demo se encontraron y corrigieron ademas:** conflicto de puerto de
Postgres, un `docker compose restart` que no recogia cambios de `.env`, un `ENUM` de
Postgres duplicado en la migracion, un desalineamiento cliente/servidor de ChromaDB, un
umbral de similitud del RAG calibrado con datos sinteticos en vez de un modelo de
embeddings real, y el archivo de normativa de ejemplo faltante dentro del contenedor.
El detalle tecnico completo de cada uno esta en ADR-006 y ADR-008 de
`docs/decisiones-tecnicas.md`.
