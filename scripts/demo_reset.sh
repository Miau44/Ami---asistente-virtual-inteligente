#!/usr/bin/env bash
# Reinicia el entorno de demo: baja los contenedores, limpia volumenes de datos,
# reconstruye, corre migraciones y siembra datos ficticios.
set -euo pipefail

cd "$(dirname "$0")/.."

echo ">> Deteniendo contenedores y limpiando volumenes de datos..."
docker compose down -v

echo ">> Reconstruyendo imagenes..."
docker compose build

echo ">> Levantando dependencias (postgres, redis, chroma)..."
docker compose up -d postgres redis chroma

echo ">> Esperando a que postgres este listo..."
until docker compose exec -T postgres pg_isready -U ami -d ami_copiloto > /dev/null 2>&1; do
  sleep 1
done

echo ">> Aplicando migraciones..."
docker compose run --rm api alembic upgrade head

echo ">> Sembrando datos de demo..."
docker compose run --rm api python -m scripts.seed_data

echo ">> Ingestando normativa de ejemplo al RAG (reemplazar por normativa oficial antes de produccion)..."
docker compose run --rm api python -m app.ingestion.ingest_normativa \
  --archivo docs/normativa/ejemplo_licencia_funcionamiento.txt \
  --titulo "Requisitos de ejemplo - Licencia de Funcionamiento (demo)" \
  --numero-norma "DEMO-001" \
  --fecha-vigencia 2026-01-01 \
  --url https://lapaz.bo/tramites-y-servicios-gamlp/

echo ">> Levantando API y worker..."
docker compose up -d api worker

echo ">> Listo. API disponible en http://localhost:8000/api/v1/health"
