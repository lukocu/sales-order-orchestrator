#!/bin/sh
# Container entrypoint: migrate, then serve. Render free has no pre-deploy step,
# so migrations run on every start (alembic upgrade head is idempotent).
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
