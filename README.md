# AMI Copiloto Backend

Agente conversacional de atencion ciudadana para el Gobierno Autonomo Municipal de La
Paz (GAMLP), Bolivia. Opera por WhatsApp: entiende el objetivo del ciudadano, arma una
ruta de tramites personalizada con RAG sobre normativa oficial, valida documentos por
foto (vision multimodal), inicia tramites contra sistemas municipales y hace
seguimiento proactivo sin que el ciudadano tenga que preguntar.

Ver diagrama de arquitectura completo en [`docs/arquitectura.md`](docs/arquitectura.md),
decisiones tecnicas (ADRs) en [`docs/decisiones-tecnicas.md`](docs/decisiones-tecnicas.md)
y el contrato de API para el equipo de frontend en
[`docs/api-contract.md`](docs/api-contract.md).

**¿Vas a hacer una demo (e-SITRAM/iGOB reales todavia no disponibles)?** Sigue
[`docs/guia-demo.md`](docs/guia-demo.md): que variables de entorno son indispensables,
como levantar el flujo completo en modo mock, y como ingestar normativa real del GAMLP
al RAG.

## Stack

Python 3.11+ · FastAPI · Pydantic v2 · PostgreSQL (SQLAlchemy 2.0 async + Alembic) ·
ChromaDB (RAG) · Google GenAI SDK (Gemini, function calling + vision) · Redis ·
APScheduler · Docker Compose · pytest · black / ruff / mypy · pre-commit · GitHub Actions.

## Arquitectura en breve

```
WhatsApp (Twilio) -> webhook -> orquestador del agente -> tools -> services -> db/integraciones
```

- `app/api`: HTTP, validacion Pydantic, auth JWT, rate limiting.
- `app/agents`: orquestador + tools del agente (registro extensible, sin if/elif gigante).
- `app/services`: logica de negocio pura, sin dependencias de FastAPI.
- `app/integrations`: interfaz abstracta `MunicipalAPIClient` + implementaciones
  mock/real intercambiables por configuracion (nunca acceso directo a BD institucionales).
- `app/workers`: motor de proactividad (stateless, idempotente).

## Arranque local (Docker, recomendado)

Requiere Docker y Docker Compose.

```bash
cp .env.example .env
# Completa al menos ANTHROPIC_API_KEY para que el agente responda con LLM real.
# Con ESITRAM_MODE=mock / IGOB_MODE=mock (default) no se necesitan credenciales
# municipales reales.

docker compose up --build
```

Esto levanta Postgres, Redis, ChromaDB, la API (con migraciones Alembic aplicadas
automaticamente) y el worker de proactividad. La API queda disponible en
`http://localhost:8000/api/v1/health`.

Para sembrar datos de demo y reiniciar el entorno desde cero:

```bash
./scripts/demo_reset.sh
```

## Arranque local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# Ajusta DATABASE_URL, REDIS_URL, CHROMA_HOST/PORT a instancias locales que ya tengas
# corriendo (o levanta solo esas dependencias con `docker compose up postgres redis chroma`).

alembic upgrade head
uvicorn app.main:app --reload
```

## Variables de entorno

Ver [`.env.example`](.env.example) para el listado completo y documentado, agrupado
por prefijo de servicio (`ANTHROPIC_*`, `TWILIO_*`, `ESITRAM_*`, `IGOB_*`, etc.).
Nunca se hardcodean secretos: todo se lee desde `.env` (ignorado por git).

## Testing

```bash
pytest                          # toda la suite (unit + integration)
pytest tests/unit                # solo unit
pytest --cov=app --cov-report=term-missing
```

La suite usa SQLite en memoria para tests de integracion (no requiere Postgres
corriendo) y mockea las integraciones municipales y el RAG donde corresponde. Incluye
un test dedicado que verifica el comportamiento anti-alucinacion del agente:
`tests/unit/test_rag_anti_hallucination.py`.

## Calidad de codigo

```bash
black app tests
ruff check app tests --fix
mypy app
pre-commit install   # corre automaticamente en cada commit
```

CI (`.github/workflows/ci.yml`) corre lint + type-check + tests en cada push/PR a `main`.

## Ingesta de normativa al RAG

```bash
python -m app.ingestion.ingest_normativa \
  --archivo docs/normativa/ordenanza_123.pdf \
  --titulo "Ordenanza Municipal 123/2024" \
  --numero-norma "OM 123/2024" \
  --fecha-vigencia 2024-01-15 \
  --url https://lapaz.bo/normativa/123
```

Divide el documento en chunks, genera embeddings en ChromaDB y registra la fuente en
Postgres (`fuentes_normativa`) para que toda respuesta del agente que cite esa norma
incluya titulo y fecha de vigencia trazables.

## Convenciones

Ver el detalle completo en `docs/decisiones-tecnicas.md`. Resumen: snake_case en
archivos/funciones Python, PascalCase en clases, tablas SQL en snake_case plural,
FKs como `tabla_singular_id`, endpoints REST en plural sin verbos y versionados
(`/api/v1/...`), commits en formato Conventional Commits, ramas
`feature/`, `fix/`, `docs/`, `refactor/`, `chore/` + kebab-case, versionado SemVer.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
