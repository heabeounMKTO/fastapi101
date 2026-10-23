#!/usr/bin/env bash
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:?POSTGRES_HOST must be set}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "Waiting for database at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until (exec 3<>"/dev/tcp/${POSTGRES_HOST}/${POSTGRES_PORT}") 2>/dev/null; do
  sleep 1
done
exec 3<&- 3>&-
echo "Database is reachable."

echo "Running alembic migrations..."
uv run alembic upgrade head

echo "Starting application..."
exec uv run main.py
