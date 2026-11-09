#!/bin/sh
# All backend quality gates, in CI order. Run in the dev container:
#   docker compose run --rm backend sh check.sh
set -e
uv sync --locked
echo "== ruff check" && uv run ruff check .
echo "== ruff format" && uv run ruff format --check .
echo "== mypy" && uv run mypy app tests
echo "== alembic" && uv run alembic upgrade head
echo "== pytest" && uv run pytest -p no:cacheprovider
