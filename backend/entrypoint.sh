#!/usr/bin/env bash
set -euo pipefail

# Apply database migrations (retry while Postgres finishes starting).
attempts=0
until alembic upgrade head; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 10 ]; then
    echo "Migrations failed after ${attempts} attempts; exiting." >&2
    exit 1
  fi
  echo "Database not ready for migrations (attempt ${attempts}/10); retrying in 3s..." >&2
  sleep 3
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
