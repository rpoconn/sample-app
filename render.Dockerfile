# Single image for Render: FastAPI serves the API and the built frontend from one origin.
# Build context is the repo root: the bun and uv workspaces and their lockfiles live there.
FROM oven/bun:1 AS frontend

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer
COPY package.json bun.lock ./
COPY frontend/package.json frontend/
COPY packages/react-email/package.json packages/react-email/
RUN bun install --frozen-lockfile

COPY frontend frontend

# Empty means same-origin requests; the backend serves the frontend itself
ENV VITE_API_URL=""

# vite.config.ts writes the build to backend/app/frontend
RUN bun run --filter frontend build

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Render terminates TLS at its proxy; trust its X-Forwarded-* headers so redirects stay https
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    FORWARDED_ALLOW_IPS="*"

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
RUN uv sync --frozen --no-dev --package app --no-install-project

COPY backend backend
RUN uv sync --frozen --no-dev --package app

COPY --from=frontend /app/backend/app/frontend backend/app/frontend

# SQLite lives here; render.yaml mounts a persistent disk over it
RUN mkdir -p /data

WORKDIR /app/backend
EXPOSE 8000

# Render sets PORT and RENDER_EXTERNAL_URL. Migrate and seed (both idempotent), then serve
CMD ["sh", "-c", "export FRONTEND_HOST=${FRONTEND_HOST:-$RENDER_EXTERNAL_URL}; bash scripts/prestart.sh && exec fastapi run --host 0.0.0.0 --port ${PORT:-8000}"]
