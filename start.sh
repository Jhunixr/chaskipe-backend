#!/bin/sh
# Arranque en produccion: primero el esquema, despues la API.
set -e

# Alembic es idempotente: si la base ya esta al dia, no hace nada.
echo "Aplicando migraciones..."
alembic upgrade head

echo "Iniciando API..."
# Sin --reload en produccion. Un solo worker: los datos viven en PostgreSQL,
# asi que se puede subir cuando haga falta.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
