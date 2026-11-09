#!/bin/sh
# Container entrypoint: migrate, sync the demo account passwords, then serve.
# Render free has no pre-deploy step, so migrations run on every start
# (alembic upgrade head is idempotent). The password sync always exits 0.
set -e
alembic upgrade head
python -m app.auth.demo_accounts
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
