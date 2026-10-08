# Build context is the repo root: uv.lock and the uv workspace live there.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
RUN uv sync --frozen --no-dev --package app --no-install-project

COPY backend backend
RUN uv sync --frozen --no-dev --package app

WORKDIR /app/backend
EXPOSE 8000

# Migrate and seed (both idempotent), then serve
CMD ["sh", "-c", "bash scripts/prestart.sh && fastapi run --host 0.0.0.0 --port 8000"]
