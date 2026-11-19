#!/bin/sh
# Container start-up script for the API.
#
#   1. Apply any pending database migrations.
#   2. Make sure the superuser from SUPERUSER_EMAIL / SUPERUSER_PASSWORD exists.
#   3. Start the web server. Extra arguments (e.g. --reload) are passed to uvicorn.
set -e

echo "==> Applying database migrations"
alembic upgrade head

echo "==> Ensuring superuser exists"
python -m app.core.bootstrap

echo "==> Starting API server"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
