# One image for local compose, CI and Render: FastAPI serves the API and the built SPA.

# --- Stage 1: build the frontend ---
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend runtime ---
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
# Dependencies first so code changes do not invalidate this layer.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Settings.static_dir defaults to /app/static (BACKEND_DIR / "static").
COPY --from=frontend /frontend/dist ./static

EXPOSE 8000
# `sh start.sh` rather than ./start.sh: does not depend on the exec bit surviving checkout.
CMD ["sh", "start.sh"]
