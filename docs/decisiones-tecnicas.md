# Decisiones Tecnicas (ADRs)

Formato: contexto / decision / consecuencias. Cada ADR queda numerado y no se edita
retroactivamente; si una decision cambia, se agrega un ADR nuevo que la reemplaza.

---

## ADR-001: Interfaz abstracta para integraciones municipales (mock/real intercambiable)

**Contexto:** durante la hackathon no hay credenciales reales de e-SITRAM/iGOB/Gestion
Documental, pero el sistema debe demostrar el flujo completo end-to-end y estar listo
para conectar credenciales reales despues sin reescribir logica de negocio.

**Decision:** `MunicipalAPIClient` es una interfaz abstracta (`app/integrations/base.py`)
con dos implementaciones por integracion (`*_client.py` real, `*_mock.py` mock),
seleccionadas por variable de entorno (`ESITRAM_MODE=mock|real`). La capa de
`services` y `agents/tools` solo dependen de la interfaz.

**Consecuencias:** cambiar de mock a real es un cambio de configuracion, no de codigo.
El costo es mantener el mock sincronizado en forma (misma estructura de respuesta) con
la API real cuando esta se defina.

---

## ADR-002: Nunca se persiste la foto de un documento

**Contexto:** los documentos de identidad/propiedad son datos sensibles. Guardarlos en
disco o en el vector store crearia una superficie de riesgo innecesaria (fuga de PII,
requisitos de retencion legal) sin aportar valor al producto: solo se necesita el
*resultado* de la validacion.

**Decision:** la foto llega como bytes en memoria (`UploadFile` en el endpoint REST, o
media descargado del webhook de WhatsApp), se envia directo a la API de vision de
Gemini, y los bytes se descartan explicitamente apenas se obtiene el resultado
(ver `app/services/documento_service.py` y `app/agents/tools/validate_document.py`).
Nunca se escribe a disco, nunca se indexa en ChromaDB, nunca se guarda en una columna
BLOB de Postgres. Solo se persiste `resultado` + `observaciones` (metadatos) en
`documentos_validados`.

**Consecuencias:** si se necesita auditoria visual retroactiva, no existe. Se acepta
ese trade-off por privacidad; si el negocio lo requiere en el futuro, deberia ser un
ADR nuevo con retencion explicita y consentimiento.

---

## ADR-003: Logging estructurado sin PII

**Contexto:** los logs de produccion suelen terminar en sistemas de menor confianza
(agregadores, dashboards de terceros) que la base transaccional. Loguear contenido de
mensajes o numeros de documento seria una fuga de datos personales de facto.

**Decision:** `app/core/logging.py` usa `structlog` con salida JSON. Las tools y
servicios loguean solo identificadores (`tramite_id`, `recordatorio_id`), resultados
(`estado`, `resultado`) y timestamps. Numeros de telefono se enmascaran
(`_mask_phone` en `whatsapp_client.py`) antes de loguearse.

**Consecuencias:** debuggear un caso especifico requiere correlacionar por
`tramite_id`/`conversacion_id` en la base de datos, no leyendo el log directamente.

---

## ADR-004: Tool registry en vez de if/elif en el orquestador

**Contexto:** el numero de tools va a crecer con cada nuevo tipo de tramite que se
soporte. Un `if/elif` gigante en el orquestador se vuelve inmanejable y acopla al
orquestador con el conocimiento de cada tramite especifico.

**Decision:** cada tool se define en su propio modulo bajo `app/agents/tools/` y se
auto-registra en un `ToolRegistry` singleton via decorador (`@tool_registry.register`).
El orquestador solo conoce `tool_registry.gemini_tools()` y
`tool_registry.ejecutar(name, input)`.

**Consecuencias:** agregar una tool nueva es agregar un archivo nuevo e importarlo en
`app/agents/tools/__init__.py`; cero cambios en `orchestrator.py`.

---

## ADR-005: Circuit breaker + timeout en clientes municipales, no reintentos infinitos

**Contexto:** si e-SITRAM/iGOB estan caidos, el agente no debe colgarse esperando
respuesta ni convertir cada mensaje del ciudadano en una cadena de timeouts largos que
degraden la experiencia de todo el sistema (y el costo de tokens del LLM en el loop
de tool use).

**Decision:** cada cliente real tiene timeout configurable
(`ESITRAM_TIMEOUT_SECONDS`, `IGOB_TIMEOUT_SECONDS`) y un circuit breaker en memoria
(`app/integrations/circuit_breaker.py`) que abre el circuito tras N fallos
consecutivos y falla rapido durante una ventana de enfriamiento. Ante fallo, se
lanza `MunicipalAPIUnavailableError`, que las tools capturan para responder con
degradacion elegante en vez de propagar un stack trace al ciudadano.

**Consecuencias:** durante una caida prolongada, el agente sistematicamente responde
"no puedo verificar esto ahora" sin reintentar agresivamente contra el sistema caido.

---

## ADR-006: RAG con umbral de similitud estricto para prevenir alucinaciones

**Contexto:** el requisito de producto es que el agente NUNCA invente requisitos,
montos o plazos. Un RAG que siempre devuelve los top-k resultados (aunque no sean
relevantes) le da al modelo material para "justificar" una alucinacion con una cita
que en realidad no aplica.

**Decision:** `RagService.buscar()` filtra los resultados de ChromaDB por
`RAG_SIMILARITY_THRESHOLD` (default 0.45) y devuelve una lista vacia si ninguno la
supera. La tool `buscar_normativa` traduce eso a `encontrado=false`. El system prompt
(`app/agents/prompts.py`) instruye al modelo a admitir la falta de informacion en ese
caso, en vez de responder con conocimiento general. Existe un test dedicado
(`tests/unit/test_rag_anti_hallucination.py`) que verifica este contrato.

La coleccion de ChromaDB se crea explicitamente con `metadata={"hnsw:space": "cosine"}`
(`app/services/rag_service.py`): sin esto, Chroma usa distancia `l2` por defecto, que
no es directamente convertible a una similitud [0,1] y produce falsos negativos
sistematicos (se detecto este bug corriendo contra un servidor Chroma real, no en los
tests unitarios que mockean `RagService`).

El valor 0.45 se calibro empiricamente contra el modelo de embeddings por defecto de
ChromaDB (`all-MiniLM-L6-v2`, descargado localmente por el propio servidor Chroma, sin
necesidad de una API de embeddings externa) usando el corpus de demo
(`docs/normativa/ejemplo_licencia_funcionamiento.txt`):

| Consulta | Similitud coseno |
|---|---|
| "requisitos licencia de funcionamiento" (relevante) | 0.54 |
| "que necesito para el catastro de mi casa" (relevante) | 0.51 |
| "requisitos para viajar a la luna" (irrelevante) | 0.38 |
| "como cocinar un pastel de chocolate" (irrelevante) | 0.20 |

**Consecuencias:** un umbral muy alto puede hacer que el agente diga "no se" en casos
donde si habia informacion util pero mal fraseada (con 0.55, la primera fila de la
tabla ya caia por debajo y producia un falso negativo). 0.45 separa con margen las
consultas relevantes de las irrelevantes en esta muestra, pero es una calibracion
inicial sobre poco contenido: al ingestar el corpus real de normativa del GAMLP
(`docs/guia-demo.md`, seccion 7) hay que volver a medir y ajustar via
`RAG_SIMILARITY_THRESHOLD` en `.env` — no es un valor universal para cualquier corpus
o modelo de embeddings.

---

## ADR-007: Autenticacion admin del dashboard simplificada para el MVP de hackathon

**Contexto:** el dashboard administrativo necesita JWT con expiracion corta, pero no
hay tiempo en el alcance de la hackathon para construir gestion completa de usuarios
administrativos (altas, bajas, roles).

**Decision:** existe un unico usuario `admin` cuya "contrasena" es el valor de
`APP_SECRET_KEY` (ver `app/api/v1/dashboard.py`). Esto es deliberadamente un
placeholder de demo, marcado explicitamente en el codigo y aqui.

**Consecuencias:** **no usar este esquema en produccion.** El siguiente paso fuera del
alcance de la hackathon es una tabla `usuarios_admin` con hash bcrypt por usuario y
roles, reutilizando integramente `app/core/security.py` (que ya genera/valida JWT de
forma generica).

---

## ADR-008: Hallazgos de correr el stack contra Docker/Postgres reales

**Contexto:** el codigo se desarrollo y se probo primero con SQLite en memoria (tests)
y sin Docker disponible en el entorno de build. Al levantar el stack completo contra
Docker real (Postgres, Redis, ChromaDB) aparecieron varios problemas que las pruebas
con mocks no podian detectar. Se documentan aqui para que no se reintroduzcan.

**Decisiones:**

1. **Enums de Postgres se serializan por `.value`, no por `.name`.** SQLAlchemy, por
   defecto, persiste el `.name` del miembro del enum de Python (ej. `"EN_REVISION"`),
   pero el tipo `ENUM` de Postgres en la migracion se creo con los `.value` en
   minuscula (`"en_revision"`). Sin `values_callable=lambda e: [x.value for x in e]`
   en cada `sa.Enum(...)` de `app/db/models/`, cualquier INSERT falla con
   `invalid input value for enum`. Los 4 modelos con enums (`tramite.py`,
   `documento_validado.py`, `recordatorio.py`, `conversacion.py`) ya lo tienen.

2. **El tipo ENUM de Postgres no debe crearse manualmente antes de `op.create_table`.**
   `op.create_table` ya crea el `ENUM` como parte del DDL de la tabla; llamar tambien a
   `enum.create(bind, checkfirst=True)` antes produce `DuplicateObjectError`. La
   migracion inicial (`app/db/migrations/versions/...`) no llama a `.create()`
   manualmente por esta razon.

3. **El puerto host de Postgres en `docker-compose.yml` es `5433`, no `5432`.** Un
   Postgres local (nativo o de otro proyecto en Docker) ocupando el 5432 del host
   rompe `docker compose up` con `port is already allocated`. La comunicacion interna
   entre contenedores (api/worker -> postgres) siempre usa el puerto 5432 del
   contenedor via DNS de compose (`postgres:5432`), asi que este remapeo solo afecta
   herramientas que se conecten desde el host.

4. **La imagen del servidor de ChromaDB debe ir alineada con el SDK de Python.** El
   `pyproject.toml` fija `chromadb>=0.5.5` sin techo, por lo que pip instala la ultima
   release del cliente (1.x); ese cliente no habla el protocolo de un servidor
   `chromadb/chroma:0.5.5` (imagen vieja fijada originalmente en `docker-compose.yml`)
   y falla con `ValueError: {"detail":"Not Found"}` al inicializar `HttpClient`. Se usa
   `chromadb/chroma:latest` para mantener cliente y servidor alineados; en produccion,
   fijar un tag exacto y actualizar ambos (cliente y servidor) juntos.

5. **`docs/` se monta como volumen en el contenedor `api`, no se copia en el
   `Dockerfile`.** `app/ingestion/ingest_normativa.py` lee archivos de
   `docs/normativa/`; como el `Dockerfile` solo copia `app/`, `alembic.ini` y
   `scripts/`, correr la ingesta sin este volumen monta falla con
   `FileNotFoundError`. El volumen tambien evita tener que rebuildear la imagen cada
   vez que se agrega o reemplaza un documento de normativa.

**Consecuencias:** todos estos problemas eran invisibles en la suite de tests (usa
SQLite y mockea RagService), lo que confirma que "los tests pasan" no es sustituto de
correr el stack real al menos una vez por cambio de infraestructura. Ver
`docs/guia-demo.md` para el procedimiento verificado de arranque.

---

## ADR-009: Migracion de Anthropic (Claude) a Google Gemini

**Contexto:** el proyecto se disenio originalmente contra la API de Anthropic
(Claude), pero para la demo del hackathon no hubo acceso a una key de Anthropic (ni a
las APIs municipales reales de e-SITRAM/iGOB, que ya estaban mockeadas por
`ESITRAM_MODE=mock`/`IGOB_MODE=mock`). Se dispuso en cambio de una API key gratuita de
Gemini (Google AI Studio).

**Decision:** se reemplazo `anthropic` por `google-genai` en todo el codigo que habla
con el modelo:

- `app/agents/orchestrator.py`: el loop de tool-use ahora es un loop de *function
  calling* de Gemini. La deteccion de "el modelo quiere llamar una tool" ya no es un
  `stop_reason == "tool_use"` (Gemini no tiene ese campo): se revisa si algun `part` de
  la respuesta trae `function_call`. El turno del modelo se reenvia tal cual
  (`contents.append(candidate.content)`) para preservar el `thought_signature` interno
  del modelo entre llamadas a tools, en vez de reconstruirlo a mano.
- `app/agents/tools/registry.py`: `anthropic_tool_specs()` -> `gemini_tools()`. Los
  `input_schema` de cada tool son JSON Schema estandar (`"type": "object"`, `"type":
  "string"`, minusculas); Gemini exige el mismo shape pero con los valores de `type` en
  MAYUSCULA (`"OBJECT"`, `"STRING"`). Se agrego un conversor recursivo en vez de
  reescribir cada schema a mano, para que las tools nuevas no tengan que preocuparse
  por el formato especifico del proveedor de LLM.
- `app/services/documento_service.py`: la validacion de documentos por vision ahora usa
  `response_mime_type="application/json"` + `response_schema` (JSON mode nativo de
  Gemini) en vez de pedirle al modelo por prompt que "responda solo JSON" y parsear con
  `json.loads` a ciegas (fragil: un modelo puede agregar texto antes/despues del JSON).
- El historial de conversacion persistido (`Mensaje.rol`) no cambio — ya se guardaba
  como texto plano por turno, no como bloques tipados de un SDK especifico — pero el
  mapeo a roles de proveedor en `app/api/v1/webhooks.py` paso de
  `"user"/"assistant"` (Anthropic/OpenAI) a `"user"/"model"` (Gemini).

**Hallazgo no obvio — cuota gratuita por alias de modelo, no por API:** contra la key
de demo, los IDs de modelo fijos (`gemini-2.0-flash`, `gemini-2.0-flash-lite`,
`gemini-2.5-flash`, `gemini-pro-latest`) devolvieron `429 RESOURCE_EXHAUSTED` con
`limit: 0` — es decir, cuota gratuita cero para esos IDs especificos en esta key/region,
no un limite ya consumido. Los alias rotativos `gemini-flash-latest` y
`gemini-flash-lite-latest` si tuvieron cuota gratuita disponible y funcionaron
(incluyendo function calling y vision, verificado en vivo). Por eso
`GEMINI_MODEL=gemini-flash-latest` es el default en `.env.example`, no un ID de modelo
fijo. Si se factura la cuenta de Google Cloud asociada a la key, probablemente todos
los IDs queden disponibles y se pueda fijar una version exacta para produccion.

**Hallazgo no obvio — "thinking" consume el presupuesto de `max_output_tokens`:** en
`DocumentoService._generate`, con el `response_schema` completo (objeto anidado de 4
campos) y `max_output_tokens=300`, la respuesta llegaba truncada o vacia
(`finish_reason=MAX_TOKENS`) porque el modelo gasto 269 de esos 300 tokens en
"pensar" antes de emitir el JSON final (`usage_metadata.thoughts_token_count`). Se
subio el limite a 500 y se desactivo el thinking para esta tarea puntual
(`thinking_config=types.ThinkingConfig(thinking_budget=0)`), ya que es una
clasificacion simple donde el razonamiento extendido no aporta precision. El
orquestador conversacional (`TramiteOrchestrator`) no desactiva thinking a proposito:
ahi si ayuda a decidir cuando llamar una tool y a seguir las reglas del system prompt.

**Reintento acotado ante sobrecarga transitoria del nivel gratuito:** durante las
pruebas en vivo aparecieron `503 UNAVAILABLE` ("high demand") y `429
RESOURCE_EXHAUSTED` intermitentes que desaparecian al reintentar la misma request
segundos despues. `app/core/gemini_retry.py` envuelve las llamadas a
`generate_content` (tanto en `TramiteOrchestrator._generate` como en
`DocumentoService._generate`) con un reintento de 3 intentos y backoff exponencial
(1-8s) usando `tenacity` (ya era dependencia del proyecto), acotado a `ServerError` y
`ClientError` con codigo 429 — nunca reintenta errores 4xx genuinos (input invalido,
etc.), mismo criterio de "reintentos acotados, no infinitos" que el circuit breaker de
integraciones municipales (ADR-005).

**Consecuencias:** la logica de negocio (`app/services/*`, RAG, tools) no cambio en
absoluto — toda la migracion quedo contenida en las tres capas que hablan directo con
el SDK del modelo. `SYSTEM_PROMPT` (`app/agents/prompts.py`) tampoco cambio: es texto
plano independiente del proveedor.

---

## ADR-010: `gemini-flash-lite-latest` en vez de `gemini-flash-latest` (cuota diaria agotada en horas)

**Contexto:** durante la primera prueba con WhatsApp real (webhook de Twilio +
ngrok), el webhook llego bien, paso la verificacion de firma y ejecuto
`buscar_normativa` correctamente, pero la llamada final al modelo fallo con `429
RESOURCE_EXHAUSTED`: `limit: 20, model: gemini-3.5-flash`. El alias
`gemini-flash-latest` (default hasta ese momento, ver ADR-009) habia rotado a
apuntar a `gemini-3.5-flash` en algun momento entre el desarrollo inicial y esta
prueba, y ese modelo especifico solo tiene 20 requests/dia gratis — cupo que ya se
habia agotado con las pruebas en vivo hechas durante el desarrollo (function
calling, vision, reintentos, etc. fueron mas de 20 llamadas en el dia).

**Decision:** `GEMINI_MODEL` default cambia a `gemini-flash-lite-latest`, que
resulto tener un cupo gratuito separado (no agotado) y se reverifico en vivo que
soporta function calling y vision con el mismo shape usado en el resto del codigo
— cero cambios de codigo, solo la variable de entorno.

**Implicacion para la demo/pitch:** los alias `-latest` de Gemini pueden rotar a
que modelo apuntan sin aviso, y cada alias/modelo tiene su **propio** cupo gratuito
diario (no es un cupo compartido por key). Esto significa que:

1. Antes de una demo importante, correr un smoke test rapido (un mensaje de prueba)
   para confirmar que el modelo configurado todavia tiene cupo ese dia — no asumir
   que "ya funciono antes" sigue siendo cierto horas despues.
2. Si el cupo se agota a mitad de una demo en vivo, la mitigacion mas rapida es
   cambiar `GEMINI_MODEL` a otro alias (`gemini-flash-latest` <->
   `gemini-flash-lite-latest`) y hacer `docker compose up -d --force-recreate api`
   para que tome el cambio (ver "Cambie una variable en .env pero no se aplica" en
   `docs/guia-demo.md`).
3. La solucion de fondo, si el pitch depende de esto, es **habilitar facturacion**
   en el proyecto de Google Cloud asociado a la API key (Google AI Studio ->
   Settings -> Plan de facturacion). Con facturacion activa el limite diario del
   nivel gratuito ya no aplica; el costo de una demo corta es minimo (centavos de
   dolar por el volumen de requests de una demo de pitch).

---

## ADR-011: Busqueda web real (Tavily) como complemento de buscar_normativa, no reemplazo

**Contexto:** el corpus de normativa ingerido para la demo (`docs/normativa/ejemplo_licencia_funcionamiento.txt`)
es deliberadamente pequeno (ver guia-demo.md), asi que `buscar_normativa` responde
`encontrado=false` para cualquier rubro o tramite que no este explicitamente cubierto
ahi (ej. "venta de electrodomesticos" especificamente, o tramites de otra entidad como
el NIT ante el SIN). Se probo primero la busqueda nativa de Google integrada en Gemini
(`types.Tool(google_search=...)`), pero el nivel gratuito de la API devuelve `429` con
cupo 0 para grounding — a diferencia de generacion de texto/vision, esa funcionalidad
especifica requiere facturacion activa. Se opto por Tavily (https://tavily.com): API de
busqueda pensada para agentes de IA, con nivel gratuito sin tarjeta (1000
busquedas/mes), verificado en vivo con consultas reales sobre tramites bolivianos.

**Decision:** se agrego una tool nueva, `buscar_en_internet`
(`app/agents/tools/search_internet.py` + `app/services/internet_search_service.py`),
que el agente puede usar cuando `buscar_normativa` no encuentra nada relevante.

**Actualizacion (v1.3.0 del prompt):** la primera version de la regla 2 le pedia al
agente decir explicitamente "esto lo encontre en internet" cuando la fuente era
`buscar_en_internet`. Para la demo/pitch se ajusto a pedido explicito: el agente ya no
menciona el nombre de ninguna herramienta ni la palabra "internet" — presenta toda la
informacion como parte de su base de conocimiento normativo del GAMLP, con la misma
seguridad sin importar el origen tecnico. Esto es una decision de **presentacion**, no
de precision: el contenido que devuelve Tavily sigue siendo real (verificado en vivo
contra fuentes `.bo`), no texto inventado por el modelo — lo que cambia es que ya no se
expone al ciudadano el mecanismo interno (RAG local vs. busqueda web) que produjo la
respuesta. Como salvaguarda minima se mantiene un cierre amable pidiendo confirmar en
la Plataforma de Atencion Ciudadana, pero enmarcado como buen habito de tramite, no
como advertencia de que el dato sea dudoso.

**Por que no reemplaza a buscar_normativa:** el valor central del producto (y el punto
mas fuerte de la demo, ver guia-demo.md seccion 5) es que el agente nunca inventa
normativa municipal — eso depende de que el corpus ingerido sea texto verificado
manualmente contra la fuente oficial (ADR-006). `buscar_en_internet` no reemplaza esa
verificacion manual del corpus oficial: solo evita dejar al ciudadano sin ninguna
orientacion cuando el corpus de demo todavia no cubre su caso. La diferencia entre
ambas fuentes sigue existiendo a nivel de codigo/logs (`agent_tool_call` registra cual
tool se uso) aunque ya no se le exponga al ciudadano en el mensaje.

**Consecuencia:** si `TAVILY_API_KEY` no esta configurada, la tool responde
`encontrado=false` (ver `_sin_resultados` en `internet_search_service.py`) en vez de
fallar — el sistema se degrada al comportamiento anterior (solo `buscar_normativa`) sin
romper nada.

---

## ADR-012: El modelo necesita que le inyecten ciudadano_id y le avisen de las fotos

**Contexto:** probando el flujo real por WhatsApp (mandar una foto de CI/NIT), el
agente respondia "no tengo una respuesta para eso en este momento" — el fallback de
`_extraer_texto` cuando el modelo no genera ningun texto. Investigando, se encontraron
dos huecos de diseño reales, presentes desde el inicio del proyecto (no introducidos
por la migracion a Gemini):

1. **El modelo nunca se entera de que llego una foto.** `imagen_actual` (contextvar)
   solo lo lee la tool `validar_documento` cuando se ejecuta — pero nada en el texto
   que ve el modelo le indica que hay una foto adjunta en este turno. El modelo no
   tiene telepatia: sin una senal explicita, no tiene motivo para siquiera considerar
   llamar a `validar_documento`.
2. **Ninguna tool que requiere `ciudadano_id` (`programar_recordatorio`) o que lo
   requeriria para crear un tramite tenia forma de conseguirlo.** El modelo no puede
   inventar un UUID, y pedirselo al ciudadano por WhatsApp ("dame tu UUID") no tiene
   sentido — un ciudadano real nunca conoce ese numero.
3. **No existia ninguna tool para crear un tramite desde la conversacion.** Solo
   `POST /tramites` (usado por el dashboard) podia crear uno. Sin un tramite_id real,
   `validar_documento` no tenia contra que registrar el resultado, y
   `consultar_estado_tramite`/`programar_recordatorio` no tenian nada que consultar.

**Decision:**

- `TramiteOrchestrator.responder()` ahora recibe `ciudadano_id` (lo resuelve
  `webhooks.py` desde el telefono, como ya hacia antes) y lo inyecta como texto en
  `system_instruction` en cada llamada ("contexto interno... ciudadano_id=..."),
  aclarando que no es un dato que el ciudadano haya dado y que no se le debe
  mencionar ni pedir.
- Cuando `imagen is not None`, se agrega una nota de texto al mensaje que ve el
  modelo (`"[El ciudadano acaba de adjuntar una foto...]"`) — asi el modelo sabe que
  debe considerar llamar a `validar_documento`, aunque la imagen en si le siga
  llegando solo a la tool (el modelo nunca "ve" los bytes, sigue sin poder inventar
  contenido de la foto).
- Se agregaron dos tools nuevas: `iniciar_tramite`
  (`app/agents/tools/start_procedure.py`, llama a `TramiteService.crear`) y
  `listar_tramites_ciudadano` (`app/agents/tools/list_citizen_procedures.py`, llama a
  `TramiteService.listar_por_ciudadano`). La segunda es la pieza que cierra el loop:
  el modelo puede recuperar el `tramite_id` (UUID interno) de un ciudadano en
  cualquier turno futuro sin tener que "recordarlo" de un mensaje anterior — util
  porque el historial persistido son solo turnos de texto (ver ADR de migracion a
  Gemini), y el UUID interno no es algo que se le muestre nunca al ciudadano (solo
  ve su `codigo_externo`, ej. "ESITRAM-MOCK-XXXX").
- `SYSTEM_PROMPT` (v1.4.0) se actualizo con reglas explicitas sobre cuando usar cada
  tool nueva y la prohibicion de mostrar el `tramite_id` (UUID) al ciudadano.

**Verificado en vivo** (con `tool_registry.ejecutar` mockeado para no depender de
Postgres en el smoke test): flujo completo mensaje -> iniciar_tramite (con
ciudadano_id correcto, sin que se le pidiera al ciudadano) -> foto de documento sin
texto -> listar_tramites_ciudadano -> validar_documento con el tramite_id correcto,
todo sin exponer ningun UUID en las respuestas.

**Consecuencia:** el ciudadano ahora puede completar el flujo entero (consultar
requisitos, iniciar su tramite, validar sus documentos, consultar estado, programar
recordatorio) sin salir de la conversacion de WhatsApp ni escribir jamas un UUID.

---

## ADR-013: Modelo de vision separado para validar documentos, y el bug del thinking_budget=0

**Contexto:** un ciudadano probando el flujo real reporto que la validacion de una
foto de NIT (buena calidad, tomada con cuidado) siempre respondia algo generico tipo
"esta borrosa, mandala de nuevo", sin extraer ningun dato. Investigando dos problemas
reales, no relacionados con la calidad real de la foto:

1. **`DocumentoService` usaba los mismos modelos que el chat** (`GEMINI_MODEL` /
   `GEMINI_FALLBACK_MODEL`, con `gemini-flash-lite-latest` primero por ser el que
   tiene mas cupo gratuito disponible, ver ADR-010). Flash-Lite prioriza velocidad y
   costo sobre precision multimodal — en un documento denso (certificado de NIT con
   texto chico, tablas) tiene peor OCR que el modelo completo.
2. **`thinking_config=ThinkingConfig(thinking_budget=0)` (agregado en ADR-009 para
   evitar que "thinking" agotara `max_output_tokens`) causa `400 INVALID_ARGUMENT`
   en `gemini-flash-latest`**, aunque funciona bien en `gemini-flash-lite-latest`. El
   modelo completo aparentemente no permite desactivar el razonamiento del todo.
   Ese 400 caia en el `except Exception` generico de `_analizar_con_vision`, que
   **nunca logueaba el tipo de error real** y siempre convertia cualquier fallo (400,
   429, timeout, lo que sea) en el mismo mensaje de dominio "no se pudo analizar el
   documento, intenta con otra foto mas clara" — indistinguible para el ciudadano
   (y para nosotros mirando logs) de un rechazo real por mala calidad de imagen.
   Verificado en vivo reproduciendo el 400 directamente contra la API.

**Decision:**

- Se agregaron `GEMINI_VISION_MODEL` (`gemini-flash-latest` por defecto) y
  `GEMINI_VISION_FALLBACK_MODEL` (`gemini-flash-lite-latest`), settings separados de
  los del chat. `DocumentoService` ahora prueba primero el modelo completo (mejor
  OCR) y cae al lite solo si se agota su cupo — al reves que el chat, que prioriza el
  lite primero porque ahi la precision multimodal no es el cuello de botella.
- `thinking_budget` paso de `0` a `128`: un presupuesto chico pero no-cero, que
  funciona en ambos modelos (verificado en vivo) sin volver a caer en el truncamiento
  de MAX_TOKENS que motivo el `0` original en ADR-009. `max_output_tokens` subio de
  500 a 800 para dejar margen.
- `_analizar_con_vision` ahora loguea `error_type` antes de convertir la excepcion en
  `DocumentValidationError`, para que un fallo de infraestructura no se disfrace de
  "foto borrosa" en los logs la proxima vez.

**Consecuencia:** la misma imagen sintetica de prueba (texto de NIT simulado) paso de
`400 INVALID_ARGUMENT` silencioso a un resultado correcto con nombre y numero
extraidos. Esto no garantiza que toda foto real sea legible — pero elimina una causa
de falso rechazo que no tenia nada que ver con la calidad de la foto.
